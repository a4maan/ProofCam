"""Local corpus review aids; automatic flags are not human approvals."""
import argparse
import collections
import concurrent.futures
import html
import io
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
from scipy.fft import dctn
from benchmark import harness
from benchmark.expand import locked_records


def fingerprints(image):
    gray=image.convert('L')
    small=np.asarray(gray.resize((9,8),Image.Resampling.LANCZOS))
    dhash=int.from_bytes(np.packbits(small[:,1:]>small[:,:-1]).tobytes(),'big')
    sampled=np.asarray(gray.resize((32,32),Image.Resampling.LANCZOS),dtype=float)
    frequencies=dctn(sampled,type=2,norm='ortho')[:8,:8].reshape(-1)
    median=np.median(frequencies[1:]);bits=frequencies>median;bits[0]=False
    phash=int.from_bytes(np.packbits(bits).tobytes(),'big')
    return dhash,phash


def candidate_pairs(rows):
    d=np.array([r['dhash'] for r in rows],dtype=np.uint64)
    p=np.array([r['phash'] for r in rows],dtype=np.uint64)
    found=[]
    # Bounded vectors; no N-by-N matrix or image data kept in memory.
    for i in range(len(rows)):
        if i+1==len(rows):continue
        close=np.flatnonzero((np.bitwise_count(d[i]^d[i+1:])<=8)&(np.bitwise_count(p[i]^p[i+1:])<=6))+i+1
        for j in close:
            if rows[i]['source_id']==rows[j]['source_id']:continue
            found.append({'left':rows[i]['id'],'right':rows[j]['id'],
                          'left_split':rows[i]['split'],'right_split':rows[j]['split'],
                          'cross_split':rows[i]['split']!=rows[j]['split'],
                          'dhash_distance':int((int(d[i])^int(d[j])).bit_count()),
                          'phash_distance':int((int(p[i])^int(p[j])).bit_count()),
                          'review_status':'unreviewed_candidate_not_confirmed_duplicate'})
    return found


def inspect(row,thumbs):
    data=harness.safe_media_path(row['path']).read_bytes()
    if harness.digest(data)!=row['sha256']:raise ValueError('source hash mismatch: '+row['id'])
    with Image.open(io.BytesIO(data)) as source:
        if source.width*source.height>20_000_000:raise ValueError('source too large')
        image=ImageOps.exif_transpose(source).convert('RGB')
        dhash,phash=fingerprints(image)
        gray=np.asarray(image.convert('L').resize((128,128)),dtype=np.uint8)
        counts=np.bincount(gray.ravel(),minlength=256);probs=counts[counts>0]/gray.size
        entropy=float(-np.sum(probs*np.log2(probs)));mean=float(gray.mean())
        tags=[]
        if mean<55:tags.append('dark_candidate')
        if entropy<4.5:tags.append('low_texture_candidate')
        if max(image.size)/min(image.size)>2.8:tags.append('extreme_aspect_ratio_candidate')
        image.thumbnail((240,180));image.save(thumbs/(row['id']+'.jpg'),quality=80)
    return dict(row,dhash=dhash,phash=phash,heuristic_flags=tags,luminance_mean=round(mean,3),
                luminance_entropy_bits=round(entropy,3),review_status='unreviewed')


def review_page(rows,out):
    # Public-source thumbnails and author metadata only; stays under ignored data/.
    cards=[]
    for r in rows:
        rid=html.escape(r['id'],quote=True)
        cards.append(f'<article data-id="{rid}" data-split="{html.escape(r["split"])}"><img loading="lazy" src="thumbs/{rid}.jpg" alt="Source {rid}"><h2>{rid}</h2><p>{html.escape(r["author"])} · {html.escape(r["title"])}</p><p>{html.escape(r["split"])} · {r["width"]} × {r["height"]}</p><p>Flags: {html.escape(", ".join(r["heuristic_flags"]) or "none")}</p><label>Review <select class="decision"><option>unreviewed</option><option>approved</option><option>exclude</option></select></label><label>Tags <input class="tags" placeholder="text, faces, night, gradient, motion-blur"></label><label>Notes <input class="notes" placeholder="Rights/content/duplicate review notes"></label></article>')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; script-src 'self'; connect-src 'none'"><title>ProofCam source review</title><style>body{font:15px system-ui;background:#eef2ee;color:#172b20;padding:24px}header{position:sticky;top:0;background:#fff;padding:12px;border:1px solid #aaa}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}article{background:white;padding:16px;border:1px solid #cbd4ce}img{width:100%;height:180px;object-fit:contain}h2{font-size:14px}p{font-size:12px;overflow-wrap:anywhere}label{display:block;margin:8px 0}input,select,button{font:inherit;padding:8px;max-width:100%}button{min-height:44px}</style><header><strong>Local review · no automatic approval</strong><p>Review rights, content, and duplicates before approving. Flags are only hints. Entries stay in memory until exported; reload loses unsaved work.</p><label>Reviewer <input id="reviewer" required></label><label>Split <select id="split"><option value="all">All</option><option>tuning</option><option>heldout</option><option>negative</option></select></label><button id="export">Export decisions locally</button><span id="message" role="status"></span></header><main>'''+''.join(cards)+'</main><script src="review.js"></script></html>'
    # Keep each local review page bounded instead of rendering 10,000 cards at once.
    prefix, remainder = page.split('<main>', 1)
    _, suffix = remainder.split('</main>', 1)
    page_count = (len(cards)+199)//200
    links = ' '.join(f'<a href="page-{i+1:03d}.html">{i+1}</a>' for i in range(page_count))
    for i in range(page_count):
        (out/f'page-{i+1:03d}.html').write_text(prefix+'<nav aria-label="Review pages">'+links+'</nav><main>'+''.join(cards[i*200:(i+1)*200])+'</main>'+suffix)
    (out/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>ProofCam review index</title><h1>Local source review</h1><p>200 sources per page. Export each page’s decisions before navigating away. No page starts approved.</p><nav>'+links+'</nav></html>')
    (out/'review.js').write_text('''"use strict";
const cards=[...document.querySelectorAll('article')];
document.getElementById('split').addEventListener('change',e=>cards.forEach(c=>{c.hidden=e.target.value!=='all'&&c.dataset.split!==e.target.value;}));
document.getElementById('export').addEventListener('click',()=>{const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer){document.getElementById('message').textContent='Enter reviewer name before exporting.';return;}const rows=cards.map(c=>({id:c.dataset.id,split:c.dataset.split,reviewer,decision:c.querySelector('.decision').value,tags:c.querySelector('.tags').value.split(',').map(x=>x.trim()).filter(Boolean),notes:c.querySelector('.notes').value}));const url=URL.createObjectURL(new Blob([JSON.stringify({reviewed_at:new Date().toISOString(),rows},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='proofcam-review-'+location.pathname.split('/').pop().replace('.html','')+'-decisions.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);document.getElementById('message').textContent='Decision file exported. No source manifest was changed.';});
''')


def run(manifests,out,summary):
    rows=[]
    for manifest in manifests:rows.extend(locked_records(manifest))
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('duplicate IDs across manifests')
    groups={}
    for r in rows:
        previous=groups.setdefault(r['source_group'],r['split'])
        if previous!=r['split']:raise ValueError('source group crosses splits')
    out=Path(out);out.mkdir(parents=True,exist_ok=False);thumbs=out/'thumbs';thumbs.mkdir()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        inspected=list(pool.map(lambda r:inspect(r,thumbs),rows))
    pairs=candidate_pairs(inspected)
    harness.dump(out/'fingerprints-private.json',inspected)
    review_page(inspected,out)
    evidence={'status':'automated_screening_not_human_approval','sources_checked':len(rows),
              'manifest_hashes':{Path(m).name:harness.digest(Path(m).read_bytes()) for m in manifests},
              'source_hash_checks':'all_passed','author_split_leakage':0,
              'declared_license_counts':dict(collections.Counter(r['license'] for r in rows)),
              'missing_attribution':sum(not all(r.get(k) for k in ('author','title','source_page','license')) for r in rows),
              'heuristic_flag_counts':dict(collections.Counter(tag for r in inspected for tag in r['heuristic_flags'])),
              'near_duplicate_candidates':pairs,'cross_split_candidate_count':sum(r['cross_split'] for r in pairs),
              'approved_by_this_scan':0,'unreviewed':len(rows),
              'thresholds':{'dhash_max_distance':8,'phash_max_distance':6},
              'limitations':['Perceptual hashes are review hints, never integrity claims',
                             'Absence of a pair is not proof of no near-duplicates',
                             'License metadata presence is not source-page/license review',
                             'Darkness is not a verified night-scene label; faces/text/motion require review']}
    harness.dump(summary,evidence)
    print(json.dumps({k:evidence[k] for k in ('sources_checked','cross_split_candidate_count','heuristic_flag_counts','unreviewed')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifests',nargs='+');p.add_argument('--out',required=True);p.add_argument('--summary',required=True)
    a=p.parse_args();run(a.manifests,a.out,a.summary)
