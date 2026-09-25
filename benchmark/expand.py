"""Versioned natural-negative expansion and original-resolution supplements.

Never changes the starter manifest. Source metadata stays local; no user files
are uploaded. Uses public dataset/CDN endpoints without credentials.
"""
import argparse
import base64
import concurrent.futures
import collections
import csv
import hashlib
import io
import json
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from PIL import Image
from benchmark import corpus, harness

ROOT = Path(__file__).resolve().parent
SEED = 'proofcam-negative-expansion-v1'


def locked_records(path):
    rows = harness.jsonl(path)
    lock = json.loads(Path(path).with_suffix('.lock.json').read_text())
    if harness.digest(Path(path).read_bytes()) != lock['manifest_sha256']:
        raise ValueError('manifest lock mismatch')
    return rows


def write_snapshot(path, rows, details):
    text = ''.join(json.dumps(r, sort_keys=True, ensure_ascii=False)+'\n' for r in sorted(rows,key=lambda x:x['id']))
    if path.exists() and path.read_text()!=text:
        raise ValueError('refusing to overwrite a different snapshot')
    path.write_text(text)
    harness.dump(path.with_suffix('.lock.json'),dict(schema=1,status='unreviewed_acquisition_snapshot',
                 manifest_sha256=harness.digest(text.encode()),counts=dict(collections.Counter(r['split'] for r in rows)),**details))


def metadata():
    path=ROOT/'data/source-metadata/openimages-validation.csv'
    starter_lock=json.loads((ROOT/'manifests/openimages-starter.lock.json').read_text())
    if harness.digest(path.read_bytes())!=starter_lock['metadata_sha256']:
        raise ValueError('source metadata changed')
    with path.open(newline='',encoding='utf-8') as f:
        return list(csv.DictReader(f))


def negatives(count):
    destination=ROOT/'manifests/openimages-negatives-v1.jsonl'
    if destination.exists():
        if len(locked_records(destination))!=count: raise ValueError('existing snapshot count differs')
        corpus.restore(destination);return
    starter=locked_records(ROOT/'manifests/openimages-starter.jsonl')
    excluded={r['source_group'] for r in starter}
    bytes_seen={r['sha256'] for r in starter};pixels_seen={r['pixel_sha256'] for r in starter}
    rows=metadata();rows.sort(key=lambda r:harness.digest((SEED+r['ImageID']).encode()))
    chosen_authors=set(excluded);candidates=[]
    for r in rows:
        group=harness.digest(corpus.author_group(r).encode())
        if r['License'].rstrip('/')!='https://creativecommons.org/licenses/by/2.0' or group in chosen_authors:continue
        candidates.append(r);chosen_authors.add(group)
    if len(candidates)<count:raise ValueError('insufficient author-disjoint sources')
    accepted=[];failures=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        offset=0
        while len(accepted)<count and offset<len(candidates):
            batch=candidates[offset:offset+min(64,count-len(accepted))];offset+=len(batch)
            futures=[pool.submit(corpus.acquire,r) for r in batch]
            for row,f in zip(batch,futures):
                try:
                    item=f.result()
                    if item['sha256'] in bytes_seen or item['pixel_sha256'] in pixels_seen:raise ValueError('duplicate content')
                    item['split']='negative';item['selection_policy']=SEED
                    accepted.append(item);bytes_seen.add(item['sha256']);pixels_seen.add(item['pixel_sha256'])
                except Exception as e:failures.append({'source_id':row['ImageID'],'reason':type(e).__name__})
            print(json.dumps({'negative_sources':len(accepted),'target':count,'excluded':len(failures)}),flush=True)
    if len(accepted)!=count:raise ValueError('could not fill requested corpus')
    write_snapshot(destination,accepted,{'seed':SEED,'exclusions':failures,
                  'starter_manifest_sha256':harness.digest((ROOT/'manifests/openimages-starter.jsonl').read_bytes()),
                  'limitations':['All sources remain unreviewed','No ProofCam watermark added; external marks not ruled out','Variants do not constitute independent natural sources']})


def validate_cdn_url(url):
    parsed=urllib.parse.urlsplit(url)
    host=parsed.hostname or ''
    if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443) or not host.endswith('.staticflickr.com'):
        raise ValueError('original image URL is not an allowed HTTPS CDN endpoint')
    return url


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate_cdn_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def original(item, meta):
    url=validate_cdn_url(meta['OriginalURL'])
    path=ROOT/'data/originals'/(item['source_id']+'.jpg')
    if path.exists():data=path.read_bytes()
    else:
        opener=urllib.request.build_opener(RestrictedRedirect)
        with opener.open(url,timeout=20) as response:data=response.read(25*1024*1024+1)
    if len(data)>25*1024*1024:raise ValueError('encoded_size_limit')
    # Historical MD5 is only an upstream version check, never integrity security.
    upstream=base64.b64decode(meta['OriginalMD5'],validate=True)
    if hashlib.md5(data,usedforsecurity=False).digest()!=upstream:raise ValueError('upstream_bytes_changed')
    with Image.open(io.BytesIO(data)) as im:
        if im.format!='JPEG':raise ValueError('not_jpeg')
        if max(im.size)<2048:raise ValueError('below_native_2048')
        if im.width*im.height>20_000_000 or max(im.size)>16384:raise ValueError('dimensions_exceed_pilot_limit')
        im.load();width,height=im.size
        pixels=harness.digest(f'{width},{height}:'.encode()+im.convert('RGB').tobytes())
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        temporary=path.with_suffix('.part');temporary.write_bytes(data);temporary.replace(path)
    result=dict(item,id=item['id']+'-original',parent_source_id=item['id'],path=str(path.relative_to(ROOT)),
                sha256=harness.digest(data),pixel_sha256=pixels,width=width,height=height,download_url=url,
                upstream_md5_matched=True,resolution_variant='original_2048plus')
    return result


def originals():
    destination=ROOT/'manifests/openimages-originals-v1.jsonl'
    if destination.exists():
        harness.audit(destination);print('Original-resolution snapshot already present and verified.');return
    starter=locked_records(ROOT/'manifests/openimages-starter.jsonl')
    by_id={r['ImageID']:r for r in metadata()}
    accepted=[];failures=[];seen_bytes=set();seen_pixels=set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for start in range(0,len(starter),24):
            batch=starter[start:start+24]
            futures=[pool.submit(original,item,by_id[item['source_id']]) for item in batch]
            for item,f in zip(batch,futures):
                try:
                    row=f.result()
                    if row['sha256'] in seen_bytes or row['pixel_sha256'] in seen_pixels:raise ValueError('duplicate_original')
                    seen_bytes.add(row['sha256']);seen_pixels.add(row['pixel_sha256']);accepted.append(row)
                except Exception as e:
                    reason=('HTTP_'+str(e.code)) if isinstance(e,urllib.error.HTTPError) else str(e) if isinstance(e,ValueError) else type(e).__name__
                    failures.append({'source_id':item['source_id'],'reason':reason})
            if any(r['reason']=='HTTP_429' for r in failures):
                print('CDN rate limited requests; stopping this acquisition without bypassing the limit.',flush=True)
                break
            print(json.dumps({'originals_processed':min(start+24,len(starter)),'qualified_2048plus':len(accepted),'excluded':len(failures)}),flush=True)
    if not accepted:raise ValueError('no qualifying originals')
    write_snapshot(destination,accepted,{'parent_manifest_sha256':harness.digest((ROOT/'manifests/openimages-starter.jsonl').read_bytes()),
                   'exclusions':failures,'limitations':['Variants of starter sources, never independent new samples','Rights/content review pending','Original URLs may expire; refuse changed bytes']})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('kind',choices=['negatives','originals']);p.add_argument('--count',type=int,default=10000)
    args=p.parse_args()
    if args.count<1:p.error('count must be positive')
    negatives(args.count) if args.kind=='negatives' else originals()
