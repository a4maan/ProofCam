"""Summarize v1/v2 development fixtures without treating them as held-out data."""
from pathlib import Path
import hashlib
import json
import math
import platform
import struct
import sys
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from benchmark.harness import quality
folder=ROOT/'benchmark/runs/native-parity-v1'
def read(path):
    data=path.read_bytes()
    return Image.frombytes('RGB',struct.unpack('>II',data[:8]),data[8:])
fixtures=[]
for line in (folder/'jobs.tsv').read_text().splitlines():
    name,_=line.split('\t')
    paths=[folder/(name+suffix+'.rgb') for suffix in ['', '-swift', '-tiled']]
    source,v1,v2=map(read,paths)
    fixtures.append(dict(fixture=name,v1=quality(source,v1),v2=quality(source,v2),
        file_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))
report=dict(candidate='ios-tiled-sign24-secded-v2',scope='Raw RGB distortion on three development fixtures, not Apple JPEG QA4 or held-out qualification',
            core_sha256=hashlib.sha256((ROOT/'ios-benchmark/Core/Sources/ProofCamCore/TiledCandidate.swift').read_bytes()).hexdigest(),fixtures=fixtures)
(ROOT/'benchmark/reports/step06-ios-tiled-quality.json').write_text(json.dumps(report,indent=2)+'\n')
v1=json.loads((ROOT/'benchmark/reports/step06-ios-simulation.json').read_text())
v2=json.loads((ROOT/'benchmark/reports/step06-ios-tiled-simulation.json').read_text())
comparison={name:dict(v1=v1['groups'].get(name),v2=values) for name,values in v2['groups'].items()}
times=sorted(row['elapsedMilliseconds'] for row in v2['results'])
summary=dict(candidate=v2['candidate'],host=platform.platform(),case_count=v2['case_count'],comparison=comparison,
    host_search_milliseconds=dict(median=times[len(times)//2],p95=times[math.ceil(len(times)*.95)-1],maximum=max(times)),
    limitations=['Development fixtures used to select strength; no independent held-out qualification','Host timings are neither iPhone predictions nor a mobile performance pass','Only three marked sources, with multiple correlated transformations','Unsupported geometric combinations and removal of every complete tile can still fail'])
(ROOT/'benchmark/reports/step06-ios-tiled-comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
