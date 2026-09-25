"""Stream a pinned negative stress suite without storing 300,000 derived files.

30 variants per natural source are correlated. Never interpret this suite as
300,000 independent natural images or report a pooled 3/N bound at that N.
"""
import argparse
import json
from pathlib import Path
from PIL import ImageFilter, ImageOps
from benchmark import harness as h
from benchmark.expand import locked_records


def operations():
    return (['original']+[f'jpeg_q{q}' for q in (90,80,70,60,50)]
            +[f'resize_{edge}' for edge in (768,512,256)]
            +[f'crop_{area}_{pos}' for area in (75,50) for pos in ('center','tl','br')]
            +['rotate_m5','rotate_p5','rotate_90','gamma_08','gamma_12','brightness_m10','brightness_p10','overlay_10',
              'synthetic_screenshot_512','synthetic_screenshot_1024','synthetic_combined',
              'blur_05','blur_15','blur_30','grayscale'])


def transform(data,operation):
    if operation.startswith('blur_'):
        sigma={'blur_05':.5,'blur_15':1.5,'blur_30':3.0}[operation]
        return h.png(h.decode(data).filter(ImageFilter.GaussianBlur(sigma))),'png'
    if operation=='grayscale':return h.png(ImageOps.grayscale(h.decode(data)).convert('RGB')),'png'
    return h.transform(data,operation)


def create_plan(manifest,out):
    path=Path(manifest).resolve();rows=locked_records(path)
    if not rows or any(r['split']!='negative' for r in rows):raise ValueError('negative-only sources required')
    for field in ('id','source_group','sha256','pixel_sha256'):
        if len({r[field] for r in rows})!=len(rows):raise ValueError('duplicate '+field)
    plan={'schema':1,'status':'recipes_prepared_not_evaluated','manifest':path.name,
          'manifest_sha256':h.digest(path.read_bytes()),'source_count':len(rows),'source_order':[r['id'] for r in rows],
          'operations':operations(),'scheduled_inputs':len(rows)*len(operations()),
          'generator_sha256':h.digest(Path(__file__).read_bytes()),'harness_sha256':h.digest(Path(h.__file__).read_bytes()),
          'full_materialization_complete':False,'decoder_evaluations':0,
          'can_use_scheduled_count_as_independent_N':False,
          'limitations':['Variants share parent images; source count is the maximum independent natural-source count',
                        'Byte-identical derived cases must be de-duplicated when aggregating actual input counts',
                        'No guarantee external dataset images lack unrelated watermarks',
                        'No recovery or false-positive result is claimed by scheduling inputs']}
    destination=Path(out)
    if destination.exists():raise FileExistsError('create a new version instead of overwriting a plan')
    h.dump(destination,plan)
    print(json.dumps({k:plan[k] for k in ('source_count','scheduled_inputs','status')},indent=2))


def load_plan(plan_path,manifest):
    plan=json.loads(Path(plan_path).read_text());rows=locked_records(manifest)
    checks=[plan['manifest_sha256']==h.digest(Path(manifest).read_bytes()),
            plan['generator_sha256']==h.digest(Path(__file__).read_bytes()),
            plan['harness_sha256']==h.digest(Path(h.__file__).read_bytes()),
            plan['source_order']==[r['id'] for r in rows],plan['operations']==operations(),
            plan['scheduled_inputs']==len(rows)*len(operations())]
    if not all(checks):raise ValueError('plan/source/code changed; create a new version')
    return plan,rows


def iter_inputs(plan_path,manifest,start,count,device):
    plan,rows=load_plan(plan_path,manifest);ops=plan['operations']
    if start<0 or count<1 or start+count>plan['scheduled_inputs']:raise ValueError('invalid range')
    current=None;data=None
    for index in range(start,start+count):
        source=rows[index//len(ops)];operation=ops[index%len(ops)]
        if current!=source['id']:
            raw=h.safe_media_path(source['path']).read_bytes()
            if h.digest(raw)!=source['sha256']:raise ValueError('source bytes changed')
            data=h.jpeg(h.load_normalized(h.safe_media_path(source['path'])));current=source['id']
        output,ext=transform(data,operation);im=h.decode(output)
        edge=min(int(operation.split('_')[-1]),max(h.decode(data).size)) if operation.startswith('synthetic_screenshot_') else max(im.size)
        row={'case_id':source['id']+'__negative_'+operation,'source_id':source['id'],'source_group':source['source_group'],
             'kind':'negative_candidate','split':'negative','expected_id':None,'device':device,'transform':operation,
             'size_bucket':'synthetic-composite' if operation=='synthetic_combined' else '1024+' if edge>=1024 else '512-1023' if edge>=512 else 'below-512',
             'sha256':h.digest(output),'pixel_sha256':h.pixel_hash(im),'width':im.width,'height':im.height,
             'synthetic_screen':operation.startswith('synthetic_'),'recipe_index':index}
        yield row,output,ext


def materialize(args):
    # Validate range and code before creating output.
    plan,_=load_plan(args.plan,args.manifest)
    if args.start<0 or args.count<1 or args.start+args.count>plan['scheduled_inputs']:raise ValueError('invalid range')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False);hashes={};rows=[];duplicates=[]
    for row,data,ext in iter_inputs(args.plan,args.manifest,args.start,args.count,args.device):
        row['path']=row['case_id']+'.'+ext
        (out/row['path']).write_bytes(data)
        if row['sha256'] in hashes:duplicates.append({'case_id':row['case_id'],'same_bytes_as':hashes[row['sha256']]})
        else:hashes[row['sha256']]=row['case_id']
        rows.append(row)
    (out/'cases.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    h.dump(out/'run.json',{'status':'materialized_not_evaluated','plan_sha256':h.digest(Path(args.plan).read_bytes()),
                          'range':[args.start,args.start+args.count],'scheduled_in_batch':len(rows),
                          'unique_bytes_in_batch':len(hashes),'duplicates':duplicates,'environment':h.environment(),
                          'warning':'Do not pool correlated variants into an independent-sample confidence bound.'})
    print(f'Materialized {len(rows)} inputs; {len(hashes)} distinct byte hashes; no decoder run.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('plan');a.add_argument('manifest');a.add_argument('--out',required=True)
    b=sub.add_parser('materialize');b.add_argument('plan');b.add_argument('manifest');b.add_argument('--start',type=int,default=0);b.add_argument('--count',type=int,default=30);b.add_argument('--device',default='desktop-local-unqualified');b.add_argument('--out',required=True)
    a=p.parse_args();create_plan(a.manifest,a.out) if a.command=='plan' else materialize(a)
