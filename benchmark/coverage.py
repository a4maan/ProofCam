"""Attach dataset-provided human category labels without inventing local approval."""
import argparse
import collections
import csv
import json
from pathlib import Path
from benchmark import harness as h
from benchmark.expand import locked_records

CATEGORIES={'/m/0dzct':'faces','/m/07s6nbt':'text','/m/01d74z':'night',
            '/m/01kyr8':'darkness','/m/017rtb':'panorama'}


def summarize(manifests,labels,classes,out):
    rows=[]
    for path in manifests:rows.extend(locked_records(path))
    by_source={r['source_id']:r for r in rows}
    if len(by_source)!=len(rows):raise ValueError('do not count resolution variants as independent sources')
    with Path(classes).open(encoding='utf-8',newline='') as f:class_names=dict(csv.reader(f))
    if not all(k in class_names for k in CATEGORIES):raise ValueError('category map absent from class vocabulary')
    labels_by_image=collections.defaultdict(lambda:collections.defaultdict(set))
    provenance=collections.Counter()
    with Path(labels).open(encoding='utf-8',newline='') as f:
        for row in csv.DictReader(f):
            if row['ImageID'] not in by_source or row['LabelName'] not in CATEGORIES:continue
            if row['Source']=='machine':continue
            value=float(row['Confidence'])
            if value not in (0,1):continue
            labels_by_image[row['ImageID']][row['LabelName']].add(value);provenance[row['Source']]+=1
    counts={split:{name:0 for name in CATEGORIES.values()} for split in ('tuning','heldout','negative')}
    per_image=[];conflicts=[]
    for source,row in sorted(by_source.items()):
        categories=[]
        for label,values in labels_by_image[source].items():
            if len(values)>1:conflicts.append({'id':row['id'],'category':CATEGORIES[label]});continue
            if values=={1.0}:categories.append(CATEGORIES[label]);counts[row['split']][CATEGORIES[label]]+=1
        per_image.append({'id':row['id'],'split':row['split'],'dataset_human_positive_categories':sorted(categories),
                          'local_review_status':'unreviewed','absent_label_means':'unknown_not_negative'})
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    (out/'labels.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in per_image))
    h.dump(out/'summary.json',{'status':'dataset_label_coverage_not_local_approval','source_count':len(rows),
                              'counts_by_split':counts,'annotation_sources':dict(provenance),'conflicts':conflicts,
                              'upstream_class_names':{k:class_names[k] for k in CATEGORIES},
                              'annotation_sha256':h.digest(Path(labels).read_bytes()),'class_names_sha256':h.digest(Path(classes).read_bytes()),
                              'annotation_url':'https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv',
                              'class_names_url':'https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions.csv',
                              'limitations':['Labels are inherited from dataset human annotations, not a new local review',
                                             'Missing labels do not establish absence of the category',
                                             'Low texture, gradients, and motion blur still require local review',
                                             'Panorama label does not prove an extreme aspect ratio',
                                             'No watermark or model performance was used to derive these labels']})
    print(json.dumps(counts,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifests',nargs='+');p.add_argument('--labels',required=True);p.add_argument('--classes',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();summarize(a.manifests,a.labels,a.classes,a.out)
