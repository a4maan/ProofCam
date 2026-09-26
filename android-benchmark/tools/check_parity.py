"""Host-JVM parity tests. Never produces Android-device measurements."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from benchmark.candidates import dct_registered as d
from benchmark.candidates import dct_baseline as base
from benchmark import harness as h


def raw(path,image):
    path.write_bytes(struct.pack('>II',*image.size)+image.convert('RGB').tobytes())


def main():
    out=ROOT/'benchmark/runs/native-parity-v1';out.mkdir(parents=True,exist_ok=True)
    y,x=np.mgrid[:384,:512]
    images=[Image.fromarray(np.stack([x%256,y%256,(x+y)%256],axis=-1).astype('uint8')),
            Image.fromarray(np.random.default_rng(26).integers(20,236,(384,512,3),dtype=np.uint8))]
    first=h.jsonl(ROOT/'benchmark/manifests/openimages-starter.jsonl')[0]
    images.append(h.load_normalized(h.safe_media_path(first['path'])))
    jobs=[];expected=[]
    for i,image in enumerate(images):
        identifier=hashlib.sha256(f'parity-fixture-{i}'.encode()).hexdigest()[:32]
        marked=d.embed(image,identifier);raw(out/f'fixture{i}.rgb',image);raw(out/f'fixture{i}-python.rgb',marked)
        jobs.append(f'fixture{i}\t{identifier}');expected.append((identifier,marked))
    (out/'jobs.tsv').write_text('\n'.join(jobs)+'\n')
    source=ROOT/'android-benchmark/app/src/main/java/org/proofcam/benchmark/DctCore.java'
    subprocess.run(['javac','--release','17','-d',str(out),str(source),str(ROOT/'android-benchmark/tools/CoreParity.java')],check=True)
    subprocess.run(['java','-cp',str(out),'org.proofcam.benchmark.CoreParity',str(out)],check=True)
    results=[]
    for i,(identifier,marked) in enumerate(expected):
        data=(out/f'fixture{i}-java.rgb').read_bytes();width,height=struct.unpack('>II',data[:8]);image=Image.frombytes('RGB',(width,height),data[8:])
        assert d.extract_view(image,'qim12_registered')==identifier
        difference=np.abs(np.asarray(image,dtype=np.int16)-np.asarray(marked,dtype=np.int16))
        # Midpoint ties can choose opposite, equally valid QIM lattice points when
        # float32 and double DCT roundoff have opposite signs. Require every
        # difference >1 to occur at such a midpoint, rather than hiding errors.
        assert difference.max()<=6
        _, _, coefficients=base.coefficients(images[i])
        payload=base.frame(identifier); wide_blocks=set()
        for yy,xx in np.argwhere(np.any(difference>1,axis=2)):
            wide_blocks.add((int(yy)//8,int(xx)//8))
        blocks_per_row=width//8
        for by,bx in wide_blocks:
            value=float(coefficients[by,bx,1,2])/12
            bit=int(payload[(by*blocks_per_row+bx)%base.FRAME_BITS])
            assert abs(value-round(value))<1e-4 and round(value)%2 != bit
        results.append({'fixture':i,'width':width,'height':height,'max_channel_difference':int(difference.max()),'different_channels':int(np.count_nonzero(difference)),'quantization_midpoint_blocks':len(wide_blocks),'python_to_java_id_match':True,'java_to_python_id_match':True,'java_roundtrip':True})
    report={'status':'host_jvm_parity_passed_not_android_qualification','candidate':'android-qim12-bilinear-v1',
            'java_core_sha256':h.digest(source.read_bytes()),'python_candidate_sha256':h.digest(Path(d.__file__).read_bytes()),
            'fixtures':results,'guards':['flat_negative','invalid_id','insufficient_capacity'],
            'limitations':['Raw RGB core comparison only','Android JPEG encoding, decoding, resampling, UI, and memory are not tested by this host test','Float32/double midpoint ties may choose opposite valid QIM lattice points; observed differences above one level must be confined to verified midpoint blocks; output images are not byte-equivalent','One source photo plus two procedural test fixtures; not a robustness or quality gate']}
    destination=ROOT/'benchmark/reports/step06-native-parity.json';h.dump(destination,report);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
