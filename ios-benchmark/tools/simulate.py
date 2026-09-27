"""Host-only Pillow transformations decoded by the actual Swift candidate."""
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import numpy as np
from PIL import Image, ImageOps
ROOT = Path(__file__).resolve().parents[2]
TILED = os.environ.get('PROOFCAM_TILED') == '1'
folder = ROOT/('benchmark/runs/ios-tiled-simulation-v2' if TILED else 'benchmark/runs/ios-simulation-v1')
folder.mkdir(parents=True, exist_ok=True)
parity = ROOT/'benchmark/runs/native-parity-v1'
inputs = []
def add(name, image, expected=None, must=False):
    filename = f'{len(inputs):04d}.rgb'
    (folder/filename).write_bytes(struct.pack('>II',*image.size)+image.convert('RGB').tobytes())
    inputs.append(dict(name=name,file=filename,expected=expected,mustRecover=must,sha256=hashlib.sha256((folder/filename).read_bytes()).hexdigest()))
for line in (parity/'jobs.tsv').read_text().splitlines():
    name, token = line.split('\t')
    raw = (parity/f'{name}-tiled.rgb' if TILED else f'{name}-swift.rgb').read_bytes()
    image = Image.frombytes('RGB',struct.unpack('>II',raw[:8]),raw[8:])
    add(name+'/native',image,token,True)
    for quality in [95,85,70]:
        data = io.BytesIO(); image.save(data,format='JPEG',quality=quality)
        add(name+f'/pillow_jpeg_{quality}',Image.open(io.BytesIO(data.getvalue())).convert('RGB'),token)
    for edge in [512,768,1024]:
        size = tuple(max(1,round(value*edge/max(image.size))) for value in image.size)
        resized = image.resize(size,Image.Resampling.BILINEAR)
        add(name+f'/resize_{edge}',resized,token)
        add(name+f'/uniform_screenshot_{edge}',ImageOps.expand(resized,border=(17,83,29,61),fill=(12,12,12)),token)
    add(name+'/crop_10percent',image.crop((image.width//10,image.height//10,image.width-image.width//10,image.height-image.height//10)),token)
    add(name+'/rotate_90',image.transpose(Image.Transpose.ROTATE_90),token)
    add(name+'/mirror',ImageOps.mirror(image),token)
    screen = Image.new('RGB',(image.width+48,image.height+144),(30,40,50)); screen.paste(image,(24,72))
    # Nonuniform chrome prevents the trivial corner-color crop from matching the media rectangle.
    screen.paste((255,255,255),(4,4,20,20))
    add(name+'/nonuniform_chrome',screen,token)
    add(name+'/manual_rectangle',screen.crop((24,72,24+image.width,72+image.height)),token,True)
    if TILED:
        for angle in [2,5,10,7,7.3,20]:
            add(name+f'/rotate_{angle}_degrees',image.rotate(angle,resample=Image.Resampling.BILINEAR),token)
        for turn in [Image.Transpose.ROTATE_180,Image.Transpose.ROTATE_270]:
            add(name+f'/quarter_turn_{turn.name}',image.transpose(turn),token)
        crop=image.crop((image.width//10,image.height//10,image.width-image.width//10,image.height-image.height//10))
        add(name+'/crop_then_half_size',crop.resize((crop.width//2,crop.height//2),Image.Resampling.BILINEAR),token)
        resized=image.resize((713,round(image.height*713/image.width)),Image.Resampling.BILINEAR)
        chrome=Image.new('RGB',(resized.width+48,resized.height+144),(30,40,50));chrome.paste(resized,(24,72));chrome.paste((255,255,255),(4,4,20,20))
        add(name+'/nonuniform_chrome_resize_713',chrome,token)
for seed in range(100):
    data = np.random.default_rng(seed+1000).integers(0,256,(192,256,3),dtype=np.uint8)
    add(f'unmarked_noise/{seed}',Image.fromarray(data))
(folder/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
source_paths=[Path(__file__),ROOT/'ios-benchmark/Core/Tests/ProofCamCoreTests/HostSimulationTests.swift',ROOT/'ios-benchmark/Core/Sources/ProofCamCore/Watermark.swift',ROOT/'ios-benchmark/Core/Sources/ProofCamCore/TiledCandidate.swift']
source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
env = dict(os.environ, PROOFCAM_SIMULATION_DIRECTORY=str(folder))
subprocess.run([sys.argv[1],'test','--package-path',str(ROOT/'ios-benchmark/Core'),'--scratch-path','/tmp/proofcam-swift-build','-c','release','--filter','HostSimulationTests'],env=env,check=True)
assert source_hashes == {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}, 'Sources changed during run; rerun for reproducible evidence'
results = json.loads((folder/'results.json').read_text())
groups = {}
for row in results:
    group = row['name'].split('/')[-1] if not row['name'].startswith('unmarked_noise/') else 'unmarked_noise'
    entry = groups.setdefault(group,dict(cases=0,matching=0,unexpected_ids=0))
    entry['cases'] += 1; entry['matching'] += row['matching']; entry['unexpected_ids'] += len(row['unexpectedIDs'])
report = dict(candidate='ios-tiled-sign24-secded-v2' if TILED else 'ios-qim12-bilinear-v1',kind='synthetic_host_simulation_not_ios_evidence',groups=groups,case_count=len(results),
    fixture_manifest_sha256=hashlib.sha256((folder/'inputs.json').read_bytes()).hexdigest(),
    source_sha256=source_hashes,
    limitations=['Three marked sources: two procedural images and one photo; transformations are not independent photos','100 procedural negatives are not a real-photo false-positive study','Pillow JPEG/resampling and synthetic chrome are not Apple codecs or real screenshots','Transform recovery failures are recorded, not hidden by the test pass status'],results=results)
(ROOT/('benchmark/reports/step06-ios-tiled-simulation.json' if TILED else 'benchmark/reports/step06-ios-simulation.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(groups,indent=2))
