"""Additional fault injection, race, parser and independent-tool checks."""
import concurrent.futures
import contextlib
import hashlib
import http.client
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

import cbor2
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from provenance.protocol import Rejected, decode, encode, key_id, message, public_bytes, sign, unpack
from provenance.service import Service
from provenance.storage import private_write
from provenance.verifier import file_hash
from provenance.http_server import make_server


class AdversarialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.now=1_800_000_000
        self.issuer=ec.generate_private_key(ec.SECP256R1())
        self.key=ec.generate_private_key(ec.SECP256R1())
        self.service=Service(self.root/'registry.sqlite',self.issuer,lambda:self.now)
        self.enroll(self.key)

    def enroll(self,key,invitation=None):
        p=message('enroll',public_key=public_bytes(key),invitation=invitation or self.service.invitation())
        return self.service.enroll(sign(p,key,'enroll'))

    def challenge(self,key=None,purpose='register'):
        p=message('challenge',session=os.urandom(16).hex(),purpose=purpose)
        return self.service.challenge(sign(p,key or self.key,'challenge'))

    def payload(self,key=None,identifier=None):
        ch=self.challenge(key)
        return message('register',id=identifier or os.urandom(16).hex(),file_sha256=hashlib.sha256(b'final bytes').hexdigest(),
                       session=ch['session'],mode='online',challenge=ch['nonce'],source='import')

    def signed(self,payload,key=None):
        return sign(payload,key or self.key,'register')

    def kill_worker(self,request,phase):
        private_write(self.root/'issuer.pem',self.issuer.private_bytes(serialization.Encoding.PEM,
                      serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        (self.root/'request.cbor').write_bytes(request)
        script='''
import os,sys
from pathlib import Path
from provenance.service import Service
from provenance.storage import load_key
import provenance.service as module
root=Path(sys.argv[1]);phase=sys.argv[2]
service=Service(root/'registry.sqlite',load_key(root/'issuer.pem'),lambda:1800000000)
if phase=='before_commit':
    def die(*args,**kwargs): os._exit(73)
    module.sign=die
service.register((root/'request.cbor').read_bytes())
os._exit(74)
'''
        result=subprocess.run([sys.executable,'-c',script,str(self.root),phase],capture_output=True,timeout=15)
        self.assertEqual(result.returncode,73 if phase=='before_commit' else 74,result.stderr)

    def test_process_death_before_commit_rolls_back(self):
        request=self.signed(self.payload());self.kill_worker(request,'before_commit')
        with contextlib.closing(self.service.connect()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT consumed FROM challenges').fetchone()[0],0)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        cert=self.service.register(request)
        self.assertEqual(unpack(cert)[0]['file_sha256'],hashlib.sha256(b'final bytes').hexdigest())

    def test_process_death_after_commit_preserves_retry(self):
        p=self.payload();request=self.signed(p);self.kill_worker(request,'after_commit')
        cert=self.service.lookup(p['id'])
        self.assertEqual(self.service.register(request),cert)
        with contextlib.closing(self.service.connect()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0],1)

    def test_enrollment_race_one_invitation_one_key(self):
        invitation=self.service.invitation()
        keys=[ec.generate_private_key(ec.SECP256R1()) for _ in range(8)]
        def attempt(key):
            try:return self.enroll(key,invitation)
            except Rejected:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(attempt,keys))
        self.assertEqual(sum(r is not None for r in results),1)

    def test_two_owners_race_for_one_id(self):
        other=ec.generate_private_key(ec.SECP256R1());self.enroll(other)
        identifier=os.urandom(16).hex()
        requests=[self.signed(self.payload(key,identifier),key) for key in [self.key,other]]
        def attempt(req):
            try:return self.service.register(req)
            except Rejected:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(attempt,requests))
        self.assertEqual(sum(r is not None for r in results),1)
        with contextlib.closing(self.service.connect()) as db:
            self.assertEqual(db.execute('SELECT SUM(consumed) FROM challenges').fetchone()[0],1)

    def test_removal_storage_failure_preserves_record_and_challenge(self):
        p=self.payload();cert=self.service.register(self.signed(p));ch=self.challenge(purpose='remove')
        request=sign(message('remove',id=p['id'],session=ch['session'],challenge=ch['nonce']),self.key,'remove')
        with contextlib.closing(self.service.connect()) as db,db:
            db.execute("CREATE TRIGGER reject_tombstone BEFORE INSERT ON tombstones BEGIN SELECT RAISE(ABORT,'test'); END")
        import sqlite3
        with self.assertRaises(sqlite3.Error):self.service.remove(request)
        self.assertEqual(self.service.lookup(p['id']),cert)
        with contextlib.closing(self.service.connect()) as db,db:db.execute('DROP TRIGGER reject_tombstone')
        self.service.remove(request)
        with self.assertRaises(Rejected):self.service.lookup(p['id'])

    def test_bit_mutations_rejected(self):
        original=self.signed(self.payload())
        for offset in range(len(original)):
            for bit in range(8):
                changed=bytearray(original);changed[offset]^=1<<bit
                with self.subTest(offset=offset,bit=bit),self.assertRaises(Rejected):
                    self.service.register(bytes(changed))
        print(f'CHECK bit_mutations={len(original)*8}', flush=True)
        # Invalid attempts must not consume the valid request's challenge.
        self.service.register(original)

    def test_deterministic_random_messages_fail_closed(self):
        rng=random.Random(20260927)
        for _ in range(2000):
            data=rng.randbytes(rng.randrange(1,1025))
            with self.assertRaises(Rejected):self.service.register(data)

    def test_signed_wrong_field_types(self):
        p=self.payload()
        bad=[None,0,-1,[],{},b'wrong','wrong']
        for field in p:
            for value in bad:
                altered=dict(p);altered[field]=value
                with self.subTest(field=field,value=value),self.assertRaises(Rejected):
                    self.service.register(self.signed(altered))
        self.service.register(self.signed(p))

    @unittest.skipUnless(shutil.which('openssl'),'OpenSSL executable required for independent CLI check')
    def test_openssl_signs_request_and_verifies_certificate(self):
        p=self.payload();body=encode(p)
        headers=encode({1:-7,4:key_id(self.key).encode('ascii')})
        preimage=encode(['Signature1',headers,b'proofcam.dev.v1.register',body])
        private_write(self.root/'client.pem',self.key.private_bytes(serialization.Encoding.PEM,
                      serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        (self.root/'input.bin').write_bytes(preimage)
        result=subprocess.run(['openssl','dgst','-sha256','-sign',str(self.root/'client.pem'),'-out',str(self.root/'signature.der'),str(self.root/'input.bin')],capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        r,s=utils.decode_dss_signature((self.root/'signature.der').read_bytes())
        request=encode(cbor2.CBORTag(18,[headers,{},body,r.to_bytes(32,'big')+s.to_bytes(32,'big')]))
        cert=self.service.register(request)
        _,_,protected,body,raw=unpack(cert)
        (self.root/'input.bin').write_bytes(encode(['Signature1',protected,b'proofcam.dev.v1.certificate',body]))
        (self.root/'signature.der').write_bytes(utils.encode_dss_signature(int.from_bytes(raw[:32],'big'),int.from_bytes(raw[32:],'big')))
        (self.root/'issuer-public.pem').write_bytes(self.issuer.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
        result=subprocess.run(['openssl','dgst','-sha256','-verify',str(self.root/'issuer-public.pem'),'-signature',str(self.root/'signature.der'),str(self.root/'input.bin')],capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        (self.root/'input.bin').write_bytes(b'tampered')
        result=subprocess.run(['openssl','dgst','-sha256','-verify',str(self.root/'issuer-public.pem'),'-signature',str(self.root/'signature.der'),str(self.root/'input.bin')],capture_output=True,timeout=10)
        self.assertNotEqual(result.returncode,0)

    def test_http_ambiguous_framing_rejected(self):
        server=make_server(self.service,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        cases=[ [('Content-Length','1'),('Content-Length','1')],
                [('Content-Length','9'*5000)],
                [('Content-Length','1'),('Transfer-Encoding','chunked')],
                [('Content-Length','1'),('Host','evil.test')],
                [('Content-Length','1'),('Content-Type','application/json')] ]
        for extra in cases:
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            try:
                c.putrequest('POST','/v1/register');c.putheader('Content-Type','application/cbor')
                for name,value in extra:c.putheader(name,value)
                c.endheaders(b'x');response=c.getresponse()
                self.assertEqual(response.status,400);decode(response.read())
            finally:c.close()

    def test_interrupted_export_does_not_publish_partial_file(self):
        destination=self.root/'pending.cbor'
        with mock.patch('provenance.storage.os.fsync',side_effect=OSError('simulated full disk')):
            with self.assertRaises(OSError):private_write(destination,b'signed request')
        self.assertFalse(destination.exists(),'A failed save must not leave a published partial request')
        private_write(destination,b'signed request')
        with self.assertRaises(FileExistsError):private_write(destination,b'replacement')
        self.assertEqual(destination.read_bytes(),b'signed request')

    @unittest.skipUnless(hasattr(os,'mkfifo'),'POSIX named pipe check')
    def test_named_pipe_rejected_without_waiting_for_writer(self):
        fifo=self.root/'pipe';os.mkfifo(fifo)
        script='''
import sys
from provenance.protocol import Rejected
from provenance.verifier import file_hash
from provenance.storage import load_key
from provenance.__main__ import read
for reader in [file_hash,load_key,read]:
    try: reader(sys.argv[1])
    except Rejected: continue
    sys.exit(1)
sys.exit(0)
'''
        result=subprocess.run([sys.executable,'-c',script,str(fifo)],capture_output=True,timeout=3)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_failed_export_preserves_existing_file_and_cleans_staging(self):
        destination=self.root/'existing.cbor';destination.write_bytes(b'original')
        with mock.patch('provenance.storage.os.fsync',side_effect=OSError('simulated full disk')):
            with self.assertRaises(OSError):private_write(destination,b'replacement')
        self.assertEqual(destination.read_bytes(),b'original')
        self.assertEqual(list(self.root.glob('.*.pending')),[])

    def test_concurrent_export_never_overwrites_winner(self):
        destination=self.root/'shared.cbor'
        def attempt(value):
            try:private_write(destination,value);return value
            except FileExistsError:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(attempt,[bytes([i])*1000 for i in range(8)]))
        winners=[value for value in results if value is not None]
        self.assertEqual(len(winners),1)
        self.assertEqual(destination.read_bytes(),winners[0])
        self.assertEqual(list(self.root.glob('.*.pending')),[])

    def test_file_size_limits_and_empty_file(self):
        from provenance.verifier import MAX_FILE
        from provenance.__main__ import read
        file=self.root/'input'
        file.touch()
        with self.assertRaisesRegex(Rejected,'empty_file'):file_hash(file)
        with file.open('wb') as stream:stream.truncate(MAX_FILE+1)
        with self.assertRaisesRegex(Rejected,'file_too_large'):file_hash(file)
        with self.assertRaises(Rejected):read(file)
