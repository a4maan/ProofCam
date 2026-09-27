"""Exercise the user-facing workflow as separate processes over real loopback HTTP."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from provenance.http_server import make_server
from provenance.service import Service
from provenance.storage import load_key


class CLITests(unittest.TestCase):
    def test_durable_file_workflow(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);state=root/'server';key=root/'device.pem'
            def cli(*args,expected=0):
                completed=subprocess.run([sys.executable,'-m','provenance',*map(str,args)],capture_output=True,text=True)
                self.assertEqual(completed.returncode,expected,completed.stderr)
                return completed.stdout
            cli('init-server','--state',state,'--out',root/'trust.cbor')
            cli('invite','--state',state,'--out',root/'invite.cbor')
            cli('keygen','--key',key)
            server=make_server(Service(state/'registry.sqlite3',load_key(state/'issuer.pem')),0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                url=f'http://127.0.0.1:{server.server_port}'
                cli('enroll','--url',url,'--key',key,'--invitation',root/'invite.cbor')
                photo=root/'photo.jpg';photo.write_bytes(b'protocol fixture; not an image decoder test')
                cli('challenge','--url',url,'--key',key,'--out',root/'challenge.cbor')
                cli('prepare','--key',key,'--file',photo,'--id','a'*32,'--challenge',root/'challenge.cbor','--out',root/'request.cbor')
                cli('submit','--url',url,'--request',root/'request.cbor','--out',root/'certificate.cbor')
                cli('submit','--url',url,'--request',root/'request.cbor','--out',root/'retry.cbor')
                self.assertEqual((root/'certificate.cbor').read_bytes(),(root/'retry.cbor').read_bytes())
                args=['verify','--file',photo,'--certificate',root/'certificate.cbor','--trust',root/'trust.cbor']
                cli(*args,expected=1)  # Default verifier refuses development trust.
                result=json.loads(cli(*args,'--allow-development'))
                self.assertEqual(result['content'],'exact_match')
                self.assertEqual(result['absence_of_ai'],'not_established')
                photo.write_bytes(b'changed image or copied watermark')
                self.assertEqual(json.loads(cli(*args,'--allow-development',expected=2))['content'],'different_bytes')
                cli('challenge','--url',url,'--key',key,'--purpose','remove','--out',root/'remove.cbor')
                cli('remove','--url',url,'--key',key,'--id','a'*32,'--challenge',root/'remove.cbor')
                cli('lookup','--url',url,'--id','a'*32,'--out',root/'lookup.cbor',expected=1)
            finally:
                server.shutdown();server.server_close();thread.join()
