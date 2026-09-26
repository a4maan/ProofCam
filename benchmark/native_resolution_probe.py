"""Bounded tuning-only probe of native-resolution variants; not independent new photos."""
import argparse
import json
import time
from pathlib import Path
from benchmark import harness as h
from benchmark.expand import locked_records
from benchmark.candidates import dct_registered as d

TRANSFORMS=['original','jpeg_q70','resize_1024','synthetic_screenshot_1024','synthetic_screenshot_512']


def run(out,parent_plan):
    plan=json.loads(parent_plan.read_text());manifest=h.ROOT/'manifests/openimages-originals-v1.jsonl'
    sources=[s for s in locked_records(manifest) if s['split']=='tuning' and s['parent_source_id'] in plan['positive_sources']]
    out.mkdir(parents=True,exist_ok=False)
    cases=[];predictions=[];qualities=[];exports=[]
    run_plan={'source_manifest_sha256':h.digest(manifest.read_bytes()),'parent_plan_sha256':h.digest(parent_plan.read_bytes()),
              'candidate_code_sha256':h.digest(Path(d.__file__).read_bytes()),'baseline_helper_sha256':plan['baseline_helper_sha256'],
              'runner_sha256':h.digest(Path(__file__).read_bytes()),'source_ids':[s['id'] for s in sources],
              'transforms':TRANSFORMS,'device':plan['device'],'environment':h.environment(),
              'limitations':['Tuning resolution variants, not new independent sources','Original variants remain visually/rights unapproved','Only five explicitly listed conditions','No physical Android or screenshot evidence','Desktop timing is diagnostic; concurrent local work']}
    h.dump(out/'plan.json',run_plan)
    for source in sources:
        path=h.safe_media_path(source['path'])
        if h.digest(path.read_bytes())!=source['sha256']:raise ValueError('Native original bytes changed')
        image=h.load_normalized(path);identifier=plan['test_ids'][source['parent_source_id']]
        data=h.jpeg(d.embed(image,identifier,'qim12_registered'));name=source['id']+'.jpg';(out/name).write_bytes(data)
        exports.append({'source_id':source['id'],'parent_source_id':source['parent_source_id'],'path':name,'sha256':h.digest(data),'expected_id':identifier})
        qualities.append({'source_id':source['id'],'parent_source_id':source['parent_source_id'],'width':image.width,'height':image.height,**h.quality(h.decode(h.jpeg(image)),h.decode(data))})
        for transform in TRANSFORMS:
            changed,_=h.transform(data,transform);decoded=h.decode(changed);case_id=source['id']+'__'+transform
            start=time.perf_counter();ids,attempts=d.extract(decoded,'qim12_registered');elapsed=(time.perf_counter()-start)*1000
            edge=min(int(transform.rsplit('_',1)[1]),max(image.size)) if transform.startswith('synthetic_screenshot_') else max(decoded.size)
            cases.append({'case_id':case_id,'source_id':source['id'],'source_group':source['source_group'],'parent_source_id':source['parent_source_id'],
                          'split':'tuning','transform':transform,'device':plan['device'],'kind':'watermarked_candidate','expected_id':identifier,
                          'sha256':h.digest(changed),'size_bucket':'1024+' if edge>=1024 else '512-1023','synthetic_screen':transform.startswith('synthetic_')})
            predictions.append({'case_id':case_id,'status':'ok','search_complete':True,'detected':bool(ids),'decoded_ids':ids,'attempts':attempts,'elapsed_ms':elapsed})
        print('Native probe:',source['id'],flush=True)
    for filename,rows in [('cases',cases),('predictions',predictions),('quality',qualities),('exports',exports)]:
        (out/(filename+'.jsonl')).write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
    report=h.score(cases,predictions);report.update(run_plan);report['source_count']=len(sources);report['actual_screenshots']=0;report['android_measurements']=0
    report['cases_sha256']=h.digest((out/'cases.jsonl').read_bytes());report['predictions_sha256']=h.digest((out/'predictions.jsonl').read_bytes())
    h.dump(out/'score.json',report)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--parent-plan',type=Path,required=True);args=parser.parse_args();run(args.out,args.parent_plan)
