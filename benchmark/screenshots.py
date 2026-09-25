"""Validate and import actual screenshot evidence without changing its bytes.

An operator's screenshot attestation is recorded, not independently proven by
this script. Synthetic fixtures never qualify as actual-device evidence.
"""
import argparse
import csv
import io
import json
import re
from pathlib import Path
from PIL import Image
from benchmark import harness as h
from benchmark.expand import locked_records

NAME=re.compile(r'^[A-Za-z0-9_-]{1,100}$')
REQUIRED=('sample_id','parent_source_id','parent_asset_id','split','media_path','sha256','permission_basis',
          'device_model','os_build','app_or_browser','app_version','display_scale_percent','media_long_edge_pixels',
          'orientation','borders_or_letterboxing','region_selection','actual_os_screenshot','captured_at','review_status',
          'media_left','media_top','media_width','media_height','evidence_kind')


def validate_rows(rows,sources,exports):
    indexed={r['id']:r for r in sources}
    expected={r['source_id']:r for r in exports}
    if len(indexed)!=len(sources) or len(expected)!=len(exports):raise ValueError('duplicate source/export mappings')
    seen=set();validated=[]
    for row in rows:
        if any(not row.get(k) for k in REQUIRED):raise ValueError('incomplete screenshot metadata')
        sid=row['sample_id']
        if not NAME.fullmatch(sid) or sid in seen:raise ValueError('invalid or duplicate sample ID')
        seen.add(sid)
        if row['actual_os_screenshot']!='true' or row['evidence_kind']!='actual_device':raise ValueError('synthetic/unattested screenshot is not actual evidence')
        if row['review_status']!='approved':raise ValueError('screenshot review incomplete')
        parent=row['parent_source_id']
        if parent not in indexed or parent not in expected:raise ValueError('unknown parent or missing watermarked export')
        if indexed[parent]['split']!=row['split'] or row['split'] not in ('tuning','heldout'):raise ValueError('screenshot cannot cross parent split or use negative source')
        export=expected[parent]
        if not isinstance(export.get('expected_id'),str) or not h.ID.fullmatch(export['expected_id']) or export['expected_id']!=row['parent_asset_id']:
            raise ValueError('parent asset identifier mismatch')
        if row['region_selection'] not in ('auto','manual','none'):raise ValueError('unknown region-selection mode')
        scale=int(row['display_scale_percent'])
        if scale not in (100,125,150):raise ValueError('unsupported display-scale bucket')
        image_path=h.safe_media_path(row['media_path']);data=image_path.read_bytes()
        if len(data)>25*1024*1024 or h.digest(data)!=row['sha256']:raise ValueError('screenshot hash/size mismatch')
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ('PNG','JPEG') or getattr(im,'n_frames',1)!=1 or im.width*im.height>20_000_000 or max(im.size)>16384:
                raise ValueError('unsupported screenshot image')
            im.load();width,height=im.size;pixel_hash=h.pixel_hash(im);ext='png' if im.format=='PNG' else 'jpg'
        x,y,w,z=[int(row[k]) for k in ('media_left','media_top','media_width','media_height')]
        if min(x,y)<0 or min(w,z)<1 or x+w>width or y+z>height:raise ValueError('media rectangle outside screenshot')
        edge=int(row['media_long_edge_pixels'])
        if edge!=max(w,z):raise ValueError('media size disagrees with rectangle')
        validated.append((row,data,ext,{'width':width,'height':height,'pixel_sha256':pixel_hash}))
    if not validated:raise ValueError('no screenshot evidence supplied')
    return validated


def ingest(args):
    sources=locked_records(args.sources)
    with Path(args.csv).open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
    if any(r.get('split')=='heldout' for r in rows) and not args.allow_heldout:
        raise ValueError('heldout screenshot use requires explicit evaluation opt-in')
    exports=h.jsonl(args.exports)
    # Check the referenced watermarked export exists and matches its hash.
    used={r.get('parent_source_id') for r in rows}
    for export in exports:
        if export['source_id'] in used:
            path=(Path(args.exports).resolve().parent/export['path']).resolve()
            if h.digest(path.read_bytes())!=export['sha256']:raise ValueError('parent export bytes changed')
    approved=validate_rows(rows,sources,exports)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False);cases=[]
    source_groups={r['id']:r['source_group'] for r in sources}
    for row,data,ext,dimensions in approved:
        filename=row['sample_id']+'.'+ext;(out/filename).write_bytes(data)
        edge=int(row['media_long_edge_pixels'])
        cases.append(dict(case_id=row['sample_id'],source_id=row['parent_source_id'],split=row['split'],
                          kind='watermarked_candidate',source_group=source_groups[row['parent_source_id']],expected_id=row['parent_asset_id'],path=filename,
                          sha256=row['sha256'],device=args.device,capture_device=row['device_model'],
                          transform='actual_screenshot',size_bucket='1024+' if edge>=1024 else '512-1023' if edge>=512 else 'below-512',
                          region_selection=row['region_selection'],display_scale_percent=int(row['display_scale_percent']),
                          media_rectangle=[int(row[k]) for k in ('media_left','media_top','media_width','media_height')],
                          synthetic_screen=False,evidence_metadata=row,**dimensions))
    (out/'cases.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in cases))
    h.dump(out/'run.json',{'status':'screenshot_intake_not_decoder_evaluation','cases':len(cases),
                          'full_input_bytes_preserved':True,'metadata_is_operator_attested':True,
                          'intake_sha256':h.digest(Path(args.csv).read_bytes()),'environment':h.environment(),
                          'claim_limit':'A selected rectangle is only a recovery aid; compare the full supplied screenshot for integrity.'})
    print(f'Imported {len(cases)} screenshot records; full original bytes preserved.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('csv');p.add_argument('--sources',required=True);p.add_argument('--exports',required=True);p.add_argument('--out',required=True);p.add_argument('--device',default='desktop-local-unqualified');p.add_argument('--allow-heldout',action='store_true')
    ingest(p.parse_args())
