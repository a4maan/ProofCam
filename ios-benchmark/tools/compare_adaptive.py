"""Compare the frozen v3 simulation and raw pixel quality with v2."""
from pathlib import Path
import hashlib
import json
import math
import struct
import sys
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmark.harness import quality
folder = ROOT / 'benchmark/runs/adaptive-fixtures-v3'
reports = ROOT / 'benchmark/reports'
def read(path):
    data = path.read_bytes()
    return Image.frombytes('RGB', struct.unpack('>II', data[:8]), data[8:])
fixtures = []
for line in (folder / 'jobs.tsv').read_text().splitlines():
    name, _ = line.split('\t')
    paths = [folder / (name + suffix + '.rgb') for suffix in ['', '-tiled', '-adaptive']]
    source, v2, v3 = map(read, paths)
    fixtures.append(dict(fixture=name, v2=quality(source, v2), v3=quality(source, v3),
                         file_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))
v2 = json.loads((reports / 'step06-ios-tiled-simulation.json').read_text())
v3 = json.loads((reports / 'step06-ios-adaptive-simulation.json').read_text())
old = {r['name']: r for r in v2['results'] if r.get('expected')}
shared = [r for r in v3['results'] if r['name'] in old]
extra = [r for r in v3['results'] if r['name'].startswith('holdout')]
times = sorted(r['elapsedMilliseconds'] for r in v3['results'])
report = dict(candidate=v3['candidate'], source_sha256=v3['source_sha256'],
    shared_marked_cases=dict(count=len(shared), v2_matching=sum(old[r['name']]['matching'] for r in shared),
                             v3_matching=sum(r['matching'] for r in shared)),
    additional_photo_cases=dict(count=len(extra), matching=sum(r['matching'] for r in extra)),
    host_search_milliseconds=dict(median=times[len(times)//2], p95=times[math.ceil(len(times)*.95)-1], maximum=max(times)),
    fixtures=fixtures, additional_photo_selection=json.loads((folder/'selection.json').read_text()),
    limitations=['Raw RGB quality, not Apple JPEG quality or visual approval',
                 'Two additional photos selected before frozen v3 evaluation; not broad independent qualification',
                 'Host timings are not iPhone performance predictions',
                 'Only the original three sources have v2 recovery comparisons; v2 pixel quality measured for all five'])
(reports / 'step06-ios-adaptive-comparison.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
