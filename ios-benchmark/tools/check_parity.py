"""Run after Android host fixtures exist; accepts the built CoreParity executable."""
import hashlib
import json
import platform
from pathlib import Path
import struct
import subprocess
import sys
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmark.candidates import dct_registered as candidate
from benchmark.candidates import dct_baseline as base
folder = ROOT/'benchmark/runs/native-parity-v1'
subprocess.run([sys.argv[1], str(folder)], check=True)
def read(path):
    data = path.read_bytes()
    return Image.frombytes('RGB', struct.unpack('>II', data[:8]), data[8:])
results = []
for row in (folder/'jobs.tsv').read_text().splitlines():
    name, expected = row.split('\t')
    image = read(folder/f'{name}-swift.rgb')
    assert candidate.extract_view(image, 'qim12_registered') == expected
    reference = read(folder/f'{name}-python.rgb')
    difference = np.abs(np.asarray(image, dtype=np.int16)-np.asarray(reference, dtype=np.int16))
    assert difference.max() <= 6
    _, _, coeff = base.coefficients(read(folder/f'{name}.rgb'))
    bits = base.frame(expected)
    blocks = {(int(y)//8,int(x)//8) for y,x in np.argwhere(np.any(difference>1,axis=2))}
    for y,x in blocks:
        value = float(coeff[y,x,1,2])/12
        assert abs(value-round(value)) < 1e-4 and round(value)%2 != int(bits[(y*(image.width//8)+x)%base.FRAME_BITS])
    results.append(dict(fixture=name, swift_to_python=True, python_to_swift=True, java_to_swift=True, swift_roundtrip=True, maximum_channel_difference=int(difference.max()), midpoint_blocks=len(blocks)))
report = dict(host_platform=platform.platform(), status='host_swift_parity_passed_not_ios_validation', fixtures=results,
    source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'ios-benchmark').rglob('*.swift'))},
    limitations=['Host core check only; no Apple SDK build or physical iPhone execution', 'Raw RGB only; Apple JPEG, orientation, UI and performance untested', 'Three fixtures, not a robustness study; midpoint rounding differs from Python'])
(ROOT/'benchmark/reports/step06-ios-parity.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
