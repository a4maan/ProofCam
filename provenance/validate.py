"""Run local protocol/Swift checks and write reviewable validation metadata."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--swift',required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    logs=root/'provenance/local/validation';logs.mkdir(parents=True,exist_ok=True)
    def run(name,command):
        result=subprocess.run(command,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (logs/(name+'.log')).write_text(result.stdout)
        if result.returncode:
            print(result.stdout[-8000:]);raise SystemExit(result.returncode)
        return result.stdout
    backend=run('backend',[sys.executable,'-m','unittest','discover','-s','provenance/tests','-v'])
    swift=run('swift',[args.swift,'test','--package-path','ios-benchmark/Core','--scratch-path',str(logs/'swift-build'),'-c','release'])
    run('app-syntax',[str(Path(args.swift).with_name('swiftc')),'-frontend','-parse',
                      'ios-benchmark/ProofCamResearch/App.swift','ios-benchmark/ProofCamResearch/CaptureProvenance.swift'])
    project=root/'ios-benchmark/ProofCamResearch.xcodeproj/project.pbxproj'
    old=project.read_bytes()
    run('project',[sys.executable,'ios-benchmark/tools/create_project.py'])
    assert project.read_bytes()==old,'Project regeneration differs'
    count=int(re.search(r'Ran (\d+) tests',backend).group(1))
    suites=re.findall(r'Executed (\d+) tests, with (\d+) tests skipped and (\d+) failures',swift)
    discovered,skipped,failures=map(int,suites[-1])
    frozen=json.loads((root/'benchmark/reports/step06-ios-adaptive-simulation.json').read_text())
    for path,digest in frozen['source_sha256'].items():
        assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest,path
    paths=list((root/'provenance').glob('*.py'))+list((root/'provenance/tests').glob('*.py'))
    paths += [root/'provenance/requirements.txt',project,root/'ios-benchmark/tools/create_project.py']
    paths += list((root/'ios-benchmark/ProofCamResearch').glob('*.swift'))
    paths += list((root/'ios-benchmark/Core/Sources/ProofCamCore').glob('Provenance*.swift'))
    paths += list((root/'ios-benchmark/Core/Tests/ProofCamCoreTests').glob('Provenance*.swift'))
    report={'scope':'Local development protocol; no production assurance or device evidence',
            'validated_at_utc':datetime.now(timezone.utc).isoformat(),'host':platform.platform(),
            'python':platform.python_version(), 'backend_tests':{'passed':count,'failures':0},
            'swift_release':{'discovered':discovered,'passed':discovered-skipped,'skipped':skipped,'failures':failures},
            'app_syntax':'passed; not Apple SDK typechecking','project_generation':'deterministic',
            'v3_simulation_source_hashes':'unchanged; no watermark algorithm modifications',
            'apple_tests':'six codec and two CryptoKit tests prepared; not run on this Linux host',
            'physical_device':'not tested','platform_attestation':'not implemented; never marked passed',
            'production_issuer':'not implemented; development rejected by default',
            'source_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
    (root/'provenance/validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))


if __name__=='__main__':main()
