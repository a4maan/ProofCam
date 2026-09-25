"""Offline photo research tools. These are not production canonicalization rules."""
import argparse
import collections
import hashlib
import io
import json
import math
import platform
import re
import struct
import sys
from pathlib import Path

import numpy as np
import PIL
from PIL import Image, ImageCms, ImageEnhance, ImageOps, ImageDraw, features
import scipy
from scipy.ndimage import gaussian_filter

ROOT = Path(__file__).resolve().parent
ID = re.compile(r'^[0-9a-f]{32}$')
Image.MAX_IMAGE_PIXELS = 20_000_000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def jsonl(path):
    with Path(path).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')


def pixel_hash(im):
    im = im.convert('RGB')
    return digest(b'PROOFCAM-RESEARCH-PIXELS-v1\0' + struct.pack('>II', *im.size) + im.tobytes())


def environment():
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'pillow': PIL.__version__, 'numpy': np.__version__, 'scipy': scipy.__version__,
            'jpeg_library': features.version('jpg'),
            'libjpeg_turbo': features.version('libjpeg_turbo'),
            'harness_sha256': digest(Path(__file__).read_bytes())}


def safe_media_path(relative):
    p = (ROOT / relative).resolve()
    if not p.is_relative_to((ROOT / 'data').resolve()):
        raise ValueError('media path must stay inside benchmark/data')
    return p


def audit(manifest, verify_files=True):
    lock_path = Path(manifest).with_suffix('.lock.json')
    if not lock_path.exists():
        raise ValueError('manifest lock missing')
    lock = json.loads(lock_path.read_text())
    if lock['manifest_sha256'] != digest(Path(manifest).read_bytes()):
        raise ValueError('manifest lock mismatch')
    rows = jsonl(manifest)
    ids, hashes, pixels, groups = set(), set(), set(), {}
    for r in rows:
        for key in ('id','source_group','split','sha256','pixel_sha256','license','review_status','path'):
            if not r.get(key):
                raise ValueError(f'missing {key}')
        if r['split'] not in ('tuning','heldout','negative'):
            raise ValueError('invalid split')
        if r['id'] in ids or r['sha256'] in hashes or r['pixel_sha256'] in pixels:
            raise ValueError('duplicate id, file, or decoded pixels')
        ids.add(r['id']); hashes.add(r['sha256']); pixels.add(r['pixel_sha256'])
        group = r['source_group']
        if group in groups and groups[group] != r['split']:
            raise ValueError('source-group leakage between splits')
        groups[group] = r['split']
        if verify_files and digest(safe_media_path(r['path']).read_bytes()) != r['sha256']:
            raise ValueError(f'content lock mismatch: {r["id"]}')
    counts = dict(collections.Counter(r['split'] for r in rows))
    return {'counts': counts, 'manifest_sha256': digest(Path(manifest).read_bytes()),
            'source_group_disjoint': True, 'byte_and_manifest_pixel_duplicates': 0,
            'unreviewed': sum(r['review_status'] != 'approved' for r in rows),
            'release_ready': False,
            'release_blockers': ['Human rights/content/near-duplicate review', 'Real-device screenshot matrix',
                                '300000 eligible unmarked-input search evaluation', 'Frozen decoder and thresholds']}


def load_normalized(path):
    if path.stat().st_size > 25 * 1024 * 1024:
        raise ValueError('encoded file too large')
    with Image.open(path) as source:
        if source.format not in ('JPEG','PNG') or getattr(source, 'n_frames', 1) != 1:
            raise ValueError('unsupported source format')
        if source.width * source.height > 20_000_000 or max(source.size) > 16_384:
            raise ValueError('dimensions exceed bounds')
        source.load()
        im = ImageOps.exif_transpose(source)
        # Research preprocessing, explicitly separate from production INT1.
        if 'A' in im.getbands():
            background = Image.new('RGBA', im.size, (255,255,255,255))
            im = Image.alpha_composite(background, im.convert('RGBA')).convert('RGB')
        if source.info.get('icc_profile'):
            profile = ImageCms.ImageCmsProfile(io.BytesIO(source.info['icc_profile']))
            im = ImageCms.profileToProfile(im, profile, ImageCms.createProfile('sRGB'), outputMode='RGB')
        else:
            im = im.convert('RGB')
        im.thumbnail((2048,2048), Image.Resampling.LANCZOS)
        im.info.clear()
        return im.copy()


def jpeg(im, quality=95):
    output = io.BytesIO()
    im.save(output, format='JPEG', quality=quality, subsampling=2, optimize=False, progressive=False)
    return output.getvalue()


def png(im):
    output = io.BytesIO(); im.save(output, format='PNG', optimize=False, compress_level=6)
    return output.getvalue()


def decode(data):
    with Image.open(io.BytesIO(data)) as im:
        im.load(); return im.convert('RGB')


def strip_metadata(data):
    """Drop APP1, APP13 and COM before SOS; preserve encoded scan and rendering markers."""
    if data[:2] != b'\xff\xd8':
        raise ValueError('not JPEG')
    output = bytearray(data[:2]); pos = 2
    while pos < len(data):
        start = pos
        if data[pos] != 255:
            raise ValueError('invalid JPEG marker')
        while pos < len(data) and data[pos] == 255:
            pos += 1
        if pos >= len(data):
            raise ValueError('truncated marker')
        marker = data[pos]; pos += 1
        if marker == 0xDA:  # Copy the entire scan untouched.
            output.extend(data[start:]); return bytes(output)
        if marker == 0xD9:
            output.extend(data[start:pos]); return bytes(output)
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            output.extend(data[start:pos]); continue
        if pos + 2 > len(data):
            raise ValueError('truncated segment')
        length = int.from_bytes(data[pos:pos+2], 'big')
        end = pos + length
        if length < 2 or end > len(data):
            raise ValueError('invalid segment length')
        if marker not in (0xE1, 0xED, 0xFE):
            output.extend(data[start:end])
        pos = end
    raise ValueError('missing scan/end marker')


def resize(im, edge):
    scale = min(1, edge/max(im.size))  # Never synthesize large-source eligibility.
    return im.resize((max(1,round(im.width*scale)), max(1,round(im.height*scale))), Image.Resampling.LANCZOS)


def crop(im, area, position):
    w=max(1,round(im.width*math.sqrt(area))); h=max(1,round(im.height*math.sqrt(area)))
    offsets={'center':((im.width-w)//2,(im.height-h)//2),'tl':(0,0),'br':(im.width-w,im.height-h)}
    x,y=offsets[position]; return im.crop((x,y,x+w,y+h))


def screenshot_sim(im, edge):
    media=resize(im,edge)
    canvas=Image.new('RGB',(media.width+48,media.height+120),(32,32,32))
    canvas.paste(media,(24,60)); return canvas


def transforms():
    result=['original','metadata_strip']
    result += [f'jpeg_q{q}' for q in (90,70,50)]
    result += [f'resize_{e}' for e in (2048,1024,512,256)]
    result += [f'crop_{area}_{pos}' for area in (75,50,25) for pos in ('center','tl','br')]
    result += ['rotate_m5','rotate_p5','rotate_90','gamma_08','gamma_12','brightness_m10','brightness_p10','overlay_10']
    result += ['synthetic_screenshot_512','synthetic_screenshot_1024','synthetic_combined']
    return result


def transform(data, case):
    if case=='original': return data,'jpg'
    if case=='metadata_strip': return strip_metadata(data),'jpg'
    im=decode(data)
    if case.startswith('jpeg_q'): return jpeg(im,int(case[6:])),'jpg'
    if case.startswith('resize_'): im=resize(im,int(case.split('_')[1]))
    elif case.startswith('crop_'):
        _,area,pos=case.split('_'); im=crop(im,int(area)/100,pos)
    elif case.startswith('rotate_'):
        angle={'rotate_m5':-5,'rotate_p5':5,'rotate_90':90}[case]
        im=im.transpose(Image.Transpose.ROTATE_90) if angle==90 else im.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=(0,0,0))
    elif case.startswith('gamma_'):
        exponent={'gamma_08':.8,'gamma_12':1.2}[case]
        lut=[round(255*(i/255)**exponent) for i in range(256)]; im=im.point(lut*3)
    elif case.startswith('brightness_'): im=ImageEnhance.Brightness(im).enhance(.9 if case.endswith('m10') else 1.1)
    elif case=='overlay_10':
        # Top horizontal bar covers approximately 10% of pixels.
        ImageDraw.Draw(im).rectangle((0,0,im.width-1,max(0,round(im.height*.1)-1)),fill=(255,255,255))
    elif case.startswith('synthetic_screenshot_'): im=screenshot_sim(im,int(case.split('_')[-1]))
    elif case=='synthetic_combined':
        im=screenshot_sim(im,1024); im=crop(im,.75,'center'); im=resize(im,1024)
        return jpeg(im,70),'jpg'
    else: raise ValueError('unknown transform')
    return png(im),'png'


def build(args):
    manifest=Path(args.manifest)
    checked=audit(manifest)
    if args.split=='heldout' and not args.allow_heldout:
        raise ValueError('heldout is reserved; use --allow-heldout only after candidate/threshold freeze')
    selected=[r for r in jsonl(manifest) if r['split']==args.split]
    if args.limit: selected=selected[:args.limit]
    if not selected: raise ValueError('empty split')
    out=Path(args.out); out.mkdir(parents=True,exist_ok=False)
    cases=[]
    # Optional real candidate exports are indexed by source id, not inferred.
    exports={}
    if args.exports:
        seen_expected_ids = set()
        for r in jsonl(args.exports):
            if r['source_id'] in exports or not ID.fullmatch(r['expected_id']):
                raise ValueError('duplicate source or invalid expected 128-bit identifier')
            if r['expected_id'] in seen_expected_ids:
                raise ValueError('each exported asset requires a unique identifier')
            seen_expected_ids.add(r['expected_id'])
            exports[r['source_id']]=r
        if not all(r['id'] in exports for r in selected): raise ValueError('missing candidate exports')
        if args.split=='negative': raise ValueError('never watermark the negative corpus')
    for item in selected:
        if args.exports:
            entry=exports[item['id']]
            path=(Path(args.exports).resolve().parent/entry['path']).resolve()
            data=path.read_bytes()
            if digest(data)!=entry['sha256']: raise ValueError('candidate export hash mismatch')
            if len(data)>25*1024*1024: raise ValueError('export too large')
            with Image.open(io.BytesIO(data)) as im:
                if im.format!='JPEG' or im.width*im.height>20_000_000 or max(im.size)>2048:
                    raise ValueError('unsupported candidate export dimensions/format')
            expected=entry['expected_id']; kind='watermarked_candidate'
        else:
            data=jpeg(load_normalized(safe_media_path(item['path'])))
            expected=None; kind='negative_candidate' if args.split=='negative' else 'unwatermarked_harness_smoke'
        # Only one input transformation per experiment row; no decoder search here.
        for case in transforms():
            transformed,ext=transform(data,case)
            target=out/(item['id']+'__'+case+'.'+ext); target.write_bytes(transformed)
            image=decode(transformed)
            media_edge = min(int(case.split('_')[-1]), max(decode(data).size)) if case.startswith('synthetic_screenshot_') else max(image.size)
            size_bucket = 'synthetic-composite' if case=='synthetic_combined' else '1024+' if media_edge>=1024 else '512-1023' if media_edge>=512 else 'below-512'
            cases.append({'case_id':item['id']+'__'+case,'source_id':item['id'],
                          'split':item['split'],'source_group':item['source_group'],'device':args.device,'source_capture_device':item['device'],'transform':case,
                          'kind':kind,'expected_id':expected,'path':target.name,
                          'sha256':digest(transformed),'pixel_sha256':pixel_hash(image),
                          'baseline_sha256':digest(data),'width':image.width,'height':image.height,
                          'media_long_edge':media_edge,'size_bucket':size_bucket,
                          'synthetic_screen':case.startswith('synthetic_')})
    (out/'cases.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in cases))
    dump(out/'run.json',{'schema':1,'status':'prepared_not_evaluated','environment':environment(),
                        'corpus':checked,'split':args.split,'source_count':len(selected),
                        'case_count':len(cases),'cases_sha256':digest((out/'cases.jsonl').read_bytes()),
                        'exports_manifest_sha256':digest(Path(args.exports).read_bytes()) if args.exports else None,
                        'encoder':{'quality':95,'subsampling':2,'progressive':False,'optimize':False},
                        'limitations':['Synthetic screens are not actual screenshot evidence',
                                       'Research pixel hashes are not production canonicalization',
                                       'No decoder/candidate has been run by this command']})
    print(f'Prepared {len(cases)} cases from {len(selected)} sources: {out}')


def wilson(successes,n):
    if n==0: return None
    z=1.959963984540054; p=successes/n; divisor=1+z*z/n
    center=(p+z*z/(2*n))/divisor
    spread=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/divisor
    return [max(0,center-spread),min(1,center+spread)]


def zero_upper(n):
    return -math.expm1(math.log(.05)/n) if n else None


def score(cases, predictions):
    """Count all scheduled inputs; missing/error results cannot disappear from denominator."""
    by_id={r['case_id']:r for r in cases}
    if len(by_id)!=len(cases) or not cases: raise ValueError('duplicate/empty cases')
    for c in cases:
        if c['kind'] not in ('watermarked_candidate','negative_candidate','unwatermarked_harness_smoke'):
            raise ValueError('unknown case kind')
        if c['kind']=='watermarked_candidate':
            if not isinstance(c.get('expected_id'),str) or not ID.fullmatch(c['expected_id']):
                raise ValueError('invalid expected identifier')
        elif c.get('expected_id') is not None:
            raise ValueError('negative/smoke cases cannot have a watermark identifier')
    pred={}
    for p in predictions:
        if p['case_id'] not in by_id or p['case_id'] in pred: raise ValueError('unknown/duplicate prediction')
        if p.get('status') not in ('ok','error','timeout','unsupported'): raise ValueError('invalid prediction status')
        if type(p.get('search_complete')) is not bool or type(p.get('detected')) is not bool:
            raise ValueError('explicit boolean detection/search status required')
        if p['status']=='ok' and not p['search_complete']: raise ValueError('ok requires full declared search completion')
        ids=p.get('decoded_ids')
        if not isinstance(ids,list) or any(not isinstance(i,str) or not ID.fullmatch(i) for i in ids):
            raise ValueError('decoded_ids must contain complete 128-bit hex identifiers')
        if ids and not p['detected']: raise ValueError('recovered ID contradicts detection=false')
        elapsed=p.get('elapsed_ms')
        if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<0:
            raise ValueError('invalid elapsed time')
        pred[p['case_id']]=p
    buckets={}
    for c in cases:
        # Keep transform, device, and kind separate; never average away a failing bucket.
        key=(c['transform'],c['device'],c['kind'],c.get('size_bucket','unspecified'),
             c.get('capture_device','not_applicable'),c.get('region_selection','not_applicable'),c.get('display_scale_percent','not_applicable'))
        b=buckets.setdefault(key,{'n':0,'complete':0,'correct_id':0,'wrong_id':0,'detected':0,'missing_or_error':0,'latencies':[],'sources':set(),'byte_hashes':set()})
        b['n']+=1;b['sources'].add(c.get('source_group',c['source_id']));b['byte_hashes'].add(c.get('sha256',c['case_id']));p=pred.get(c['case_id'])
        if p and (p['detected'] or p['decoded_ids']): b['detected']+=1
        if p and any(i!=c['expected_id'] for i in p['decoded_ids']): b['wrong_id']+=1
        complete=p and p['status']=='ok' and p['search_complete']
        if not complete: b['missing_or_error']+=1;continue
        b['complete']+=1;b['latencies'].append(p['elapsed_ms'])
        # Ambiguous results containing a wrong ID are not counted as successful recovery.
        if c['expected_id'] and set(p['decoded_ids'])=={c['expected_id']}: b['correct_id']+=1
    report=[]
    for (transform_name,device,kind,size_bucket,capture_device,region_selection,display_scale),b in sorted(buckets.items(),key=lambda item:str(item[0])):
        source_count=len(b.pop('sources'));times=b.pop('latencies');unique_bytes=len(b.pop('byte_hashes'))
        distinct_units=source_count==b['n'] and unique_bytes==b['n']
        b.update(transform=transform_name,device=device,kind=kind,size_bucket=size_bucket,unique_sources=source_count,unique_input_hashes=unique_bytes,
                 repeated_sources_or_bytes=not distinct_units,
                 capture_device=capture_device,region_selection=region_selection,display_scale_percent=display_scale,
                 latency_p95_ms=float(np.percentile(times,95)) if times else None,
                 recovery_rate=b['correct_id']/b['n'] if kind=='watermarked_candidate' else None,
                 recovery_wilson95=wilson(b['correct_id'],b['n']) if kind=='watermarked_candidate' and distinct_units else None)
        b['detection_wilson95']=wilson(b['detected'],b['n']) if kind=='negative_candidate' and distinct_units and b['complete']==b['n'] else None
        b['zero_detection_upper95']=zero_upper(b['n']) if kind=='negative_candidate' and distinct_units and b['complete']==b['n'] and b['detected']==0 else None
        b['approx_3_over_n']=3/b['n'] if b['zero_detection_upper95'] is not None else None
        report.append(b)
    return {'status':'research_only_not_release_certification','buckets':report,
            'wrong_record_lookup':'not_measured','false_cryptographic_acceptance':'not_measured',
            'scheduled_inputs':len(cases),'predictions_received':len(pred),
            'limitations':['Bounds assume independent representative inputs within each bucket.',
                          'Do not pool related transforms as independent natural sources.',
                          'Detector false positives and wrong IDs are not cryptographic acceptance.',
                          'Search budget, corpus eligibility, and thresholds need separate validation.']}


def quality(baseline, candidate):
    """11x11 Gaussian (sigma 1.5), population moments, RGB SSIM; valid interior."""
    a=np.asarray(baseline.convert('RGB'),dtype=np.float64)
    b=np.asarray(candidate.convert('RGB'),dtype=np.float64)
    if a.shape!=b.shape or min(a.shape[:2])<11: raise ValueError('quality requires equal images at least 11 pixels wide/high')
    kwargs={'sigma':(1.5,1.5,0),'truncate':3.5,'mode':'reflect'}
    ma=gaussian_filter(a,**kwargs);mb=gaussian_filter(b,**kwargs)
    va=np.maximum(0,gaussian_filter(a*a,**kwargs)-ma*ma)
    vb=np.maximum(0,gaussian_filter(b*b,**kwargs)-mb*mb)
    cov=gaussian_filter(a*b,**kwargs)-ma*mb
    ssim=((2*ma*mb+6.5025)*(2*cov+58.5225))/((ma*ma+mb*mb+6.5025)*(va+vb+58.5225))
    mse=float(np.mean((a-b)**2))
    return {'ssim_rgb_gaussian11':float(ssim[5:-5,5:-5].mean()),
            'psnr_db':10*math.log10(255**2/mse) if mse else None,'identical_pixels':mse==0,
            'note':'PSNR null for identical pixels (infinite); compare identically encoded unwatermarked/watermarked exports only for QA4.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('audit');a.add_argument('manifest');a.add_argument('--out')
    b=sub.add_parser('build');b.add_argument('manifest');b.add_argument('--split',choices=['tuning','heldout','negative'],default='tuning');b.add_argument('--limit',type=int,default=0);b.add_argument('--out',required=True);b.add_argument('--allow-heldout',action='store_true');b.add_argument('--exports');b.add_argument('--device',default='desktop-local-unqualified')
    s=sub.add_parser('score');s.add_argument('cases');s.add_argument('predictions');s.add_argument('--out',required=True);s.add_argument('--candidate-metadata',required=True)
    q=sub.add_parser('quality');q.add_argument('baseline');q.add_argument('candidate');q.add_argument('--out',required=True)
    args=p.parse_args()
    if args.command=='audit':
        result=audit(args.manifest)
        if args.out: dump(args.out,result)
        print(json.dumps(result,indent=2))
    elif args.command=='build':
        if args.limit<0: p.error('limit must be nonnegative')
        build(args)
    elif args.command=='score':
        metadata=json.loads(Path(args.candidate_metadata).read_text())
        for key in ('candidate','code_revision','weights_sha256_or_none','payload_layout','ecc','thresholds','search_budget','runtime','device','license'):
            if key not in metadata or metadata[key] in (None,'',{}):
                raise ValueError('candidate metadata missing: '+key)
        if 'REPLACE_WITH_' in json.dumps(metadata):
            raise ValueError('replace metadata template placeholders')
        cases=jsonl(args.cases)
        if any(c['device']!=metadata['device'] for c in cases):
            raise ValueError('candidate device must match scheduled cases')
        report=score(cases,jsonl(args.predictions))
        report.update(candidate_metadata=metadata,environment=environment(),
                      cases_sha256=digest(Path(args.cases).read_bytes()),
                      predictions_sha256=digest(Path(args.predictions).read_bytes()))
        dump(args.out,report)
    else:
        with Image.open(args.baseline) as a,Image.open(args.candidate) as b: result=quality(a,b)
        dump(args.out,result)


if __name__=='__main__':
    main()
