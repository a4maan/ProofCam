"""Preserve development sources and preselect two additional local photos for validation."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from benchmark import harness as h
old=ROOT/'benchmark/runs/native-parity-v1'
folder=ROOT/'benchmark/runs/adaptive-fixtures-v3';folder.mkdir(parents=True,exist_ok=True)
jobs=(old/'jobs.tsv').read_text().splitlines()
for row in jobs:
    name,_=row.split('\t');shutil.copyfile(old/f'{name}.rgb',folder/f'{name}.rgb')
records=h.jsonl(ROOT/'benchmark/manifests/openimages-starter.jsonl')[1:3]
selection=[]
for i,record in enumerate(records):
    name=f'holdout{i}'
    image=h.load_normalized(h.safe_media_path(record['path'])).convert('RGB')
    token=hashlib.sha256(f'proofcam-adaptive-holdout-{i}'.encode()).hexdigest()[:32]
    data=struct.pack('>II',*image.size)+image.tobytes()
    (folder/f'{name}.rgb').write_bytes(data)
    jobs.append(name+'\t'+token)
    selection.append(dict(name=name,source_path=record['path'],normalized_rgb_sha256=hashlib.sha256(data).hexdigest(),width=image.width,height=image.height))
(folder/'jobs.tsv').write_text('\n'.join(jobs)+'\n')
(folder/'selection.json').write_text(json.dumps(dict(rule='Manifest entries 1 and 2, after the existing development photo at entry 0; selected before evaluating the frozen v3 design',sources=selection),indent=2)+'\n')
print(json.dumps(selection,indent=2))
