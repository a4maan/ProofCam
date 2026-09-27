import concurrent.futures
import copy
import hashlib
import http.client
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile
import threading
import unittest

import cbor2
from cryptography.hazmat.primitives.asymmetric import ec

from provenance.protocol import *
from provenance.service import Service
from provenance.storage import create_key, load_key
from provenance.verifier import development_trust, verify_file
from provenance.http_server import make_server
from provenance.__main__ import request


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.now=1_800_000_000
        self.issuer=ec.generate_private_key(ec.SECP256R1())
        self.key=ec.generate_private_key(ec.SECP256R1())
        self.service=Service(self.root/'db.sqlite',self.issuer,lambda:self.now)
        self.invite=self.service.invitation()
        self.enrollment=sign(message('enroll',public_key=public_bytes(self.key),invitation=self.invite),self.key,'enroll')
        self.service.enroll(self.enrollment)
        self.photo=self.root/'image.jpg';self.photo.write_bytes(b'final export bytes for protocol tests')
        self.trust=development_trust(self.issuer,self.now)

    def challenge(self,key=None,purpose='register',session=None):
        return self.service.challenge(sign(message('challenge',session=session or secrets.token_hex(16),purpose=purpose),key or self.key,'challenge'))

    def registration(self,challenge=None,identifier=None,key=None,**changes):
        challenge=challenge or self.challenge(key)
        p=message('register',id=identifier or secrets.token_hex(16),file_sha256=hashlib.sha256(self.photo.read_bytes()).hexdigest(),
                  session=challenge['session'],mode='online',challenge=challenge['nonce'],source='import')
        p.update(changes)
        return sign(p,key or self.key,'register')

    def result(self,cert,**kwargs):
        return verify_file(cert,self.photo,self.trust,allow_development=True,now=self.now,**kwargs)

    def test_end_to_end_and_privacy(self):
        cert=self.service.register(self.registration())
        result=self.result(cert)
        self.assertEqual(result['content'],'exact_match')
        self.assertEqual(result['absence_of_ai'],'not_established')
        self.assertEqual(result['capture_checks']['camera_origin'],'unavailable')
        self.assertEqual(result['issuer'],'development_only')
        self.assertEqual(result['availability'],'not_checked_offline')
        p=unpack(cert)[0]
        self.assertNotIn('public_key',p);self.assertNotIn('session',p);self.assertNotIn('challenge',p)
        self.assertNotIn(key_id(self.key).encode(),cert)
        self.assertEqual(self.service.lookup(p['id']),cert)

    def test_production_rejects_development(self):
        cert=self.service.register(self.registration())
        with self.assertRaisesRegex(Rejected,'development_issuer_rejected'):
            verify_file(cert,self.photo,self.trust,now=self.now)

    def test_changed_file_and_copied_id(self):
        cert=self.service.register(self.registration())
        self.photo.write_bytes(b'AI image or different pixels with a copied watermark')
        self.assertEqual(self.result(cert)['content'],'different_bytes')
        with self.assertRaisesRegex(Rejected,'record_id_mismatch'):
            self.result(cert,expected_id='f'*32)

    def test_tamper_and_signature_domain(self):
        cert=self.service.register(self.registration())
        raw=bytearray(cert);raw[-1]^=1
        with self.assertRaises(Rejected):self.result(bytes(raw))
        with self.assertRaises(Rejected):verify(cert,self.issuer.public_key(),'register')
        raw=cbor2.loads(cert);parts=list(raw.value);payload=decode(parts[2]);payload['file_sha256']='0'*64;parts[2]=encode(payload)
        with self.assertRaises(Rejected):self.result(encode(cbor2.CBORTag(18,parts)))

    def test_enrollment_proof_and_invitation_reuse(self):
        self.assertEqual(self.service.enroll(self.enrollment)['installation'],key_id(self.key))
        other=ec.generate_private_key(ec.SECP256R1())
        with self.assertRaises(Rejected):self.service.enroll(sign(message('enroll',public_key=public_bytes(other),invitation=self.invite),other,'enroll'))
        with self.assertRaises(Rejected):self.service.enroll(sign(message('enroll',public_key=public_bytes(self.key),invitation=self.service.invitation()),other,'enroll'))
        invitation=self.service.invitation();self.now+=86400
        with self.assertRaises(Rejected):self.service.enroll(sign(message('enroll',public_key=public_bytes(other),invitation=invitation),other,'enroll'))

    def test_unenrolled_and_revoked_installation(self):
        other=ec.generate_private_key(ec.SECP256R1())
        with self.assertRaises(Rejected):self.challenge(other)
        req=self.registration();self.service.revoke(key_id(self.key))
        with self.assertRaises(Rejected):self.service.register(req)
        with self.assertRaises(Rejected):self.service.enroll(self.enrollment)

    def test_idempotency_expiry_restart_and_conflict(self):
        req=self.registration();cert=self.service.register(req);self.now+=400
        new=Service(self.root/'db.sqlite',self.issuer,lambda:self.now)
        # A fresh ECDSA signature of the same payload is also an exact retry.
        retry=sign(unpack(req)[0],self.key,'register')
        self.assertEqual(new.register(retry),cert)
        p=unpack(req)[0];p['file_sha256']='0'*64
        with self.assertRaisesRegex(Rejected,'record_conflict'):new.register(sign(p,self.key,'register'))

    def test_challenge_replay_expiry_and_binding(self):
        challenge=self.challenge();self.service.register(self.registration(challenge))
        with self.assertRaises(Rejected):self.service.register(self.registration(challenge))
        challenge=self.challenge();self.now+=300
        with self.assertRaises(Rejected):self.service.register(self.registration(challenge))
        challenge=self.challenge()
        with self.assertRaises(Rejected):self.service.register(self.registration(challenge,session='0'*32))
        with self.assertRaises(Rejected):self.service.register(self.registration(self.challenge(purpose='remove')))
        other=ec.generate_private_key(ec.SECP256R1())
        self.service.enroll(sign(message('enroll',public_key=public_bytes(other),invitation=self.service.invitation()),other,'enroll'))
        with self.assertRaises(Rejected):self.service.register(self.registration(challenge,key=other))

    def test_offline_and_claim_injection(self):
        p=unpack(self.registration())[0];p['challenge']=None;p['mode']='offline'
        cert=self.service.register(sign(p,self.key,'register'))
        self.assertEqual(self.result(cert)['capture_checks']['fresh_registration_challenge'],'not_applicable')
        for changes in [{'attestation':True},{'source':'verified_camera'},{'mode':'trusted'},{'type':'proofcam.prod.v1.register'},{'version':True}]:
            p=unpack(self.registration())[0];p.update(changes)
            with self.assertRaises(Rejected):self.service.register(sign(p,self.key,'register'))

    def test_concurrent_single_consume(self):
        challenge=self.challenge();requests=[self.registration(challenge) for _ in range(8)]
        def attempt(req):
            try:return self.service.register(req)
            except Rejected:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(attempt,requests))
        self.assertEqual(sum(r is not None for r in results),1)

    def test_concurrent_identical_retry(self):
        req=self.registration()
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(self.service.register,[req]*6))
        self.assertEqual(len(set(results)),1)

    def test_storage_failure_rolls_back_challenge(self):
        challenge=self.challenge();req=self.registration(challenge)
        with self.service.connect() as db:
            db.execute("CREATE TRIGGER reject_record BEFORE INSERT ON records BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(sqlite3.Error):self.service.register(req)
        with self.service.connect() as db:db.execute('DROP TRIGGER reject_record')
        self.assertEqual(self.result(self.service.register(req))['content'],'exact_match')

    def test_removal_owner_authorization_and_tombstone(self):
        req=self.registration();cert=self.service.register(req);identifier=unpack(cert)[0]['id']
        challenge=self.challenge(purpose='remove')
        removal=sign(message('remove',id=identifier,session=challenge['session'],challenge=challenge['nonce']),self.key,'remove')
        other=ec.generate_private_key(ec.SECP256R1())
        with self.assertRaises(Rejected):self.service.remove(sign(unpack(removal)[0],other,'remove'))
        self.service.remove(removal)
        with self.assertRaisesRegex(Rejected,'record_unavailable'):self.service.lookup(identifier)
        with self.assertRaisesRegex(Rejected,'id_unavailable'):self.service.register(req)
        with self.assertRaises(Rejected):self.service.remove(removal)
        # Public receipt still verifies its signature, never claims current availability.
        self.assertEqual(self.result(cert)['availability'],'not_checked_offline')
        with self.service.connect() as db:self.assertEqual(db.execute('SELECT * FROM tombstones').fetchall(),[(identifier,)])

    def test_unknown_revoked_stale_and_future_trust(self):
        cert=self.service.register(self.registration())
        for mutate in [lambda t:t['keys'].clear(),lambda t:t['keys'][key_id(self.issuer)].update(status='revoked'),
                       lambda t:t.update(valid_until=self.now),lambda t:t.update(valid_from=self.now+1)]:
            trust=copy.deepcopy(self.trust);mutate(trust)
            with self.assertRaises(Rejected):verify_file(cert,self.photo,trust,allow_development=True,now=self.now)
        p=unpack(cert)[0];p['checks']['camera_origin']='passed'
        with self.assertRaisesRegex(Rejected,'unsupported_assurance_claim'):self.result(sign(p,self.issuer,'certificate'))

    def test_malformed_protocol_inputs(self):
        for data in [b'',b'\xa2\x61a\x01\x61a\x02',b'\x01\x02',b'\x9f\x01\xff',b'x'*16385,b'\x81'*1000+b'\x00', b'\x9b'+b'\xff'*8, b'\x5b'+b'\xff'*8]:
            with self.assertRaises(Rejected):self.service.register(data)
        for data in [None,[],1,True,{'foo':'bar'},cbor2.CBORTag(18,[b'',{},b'',b''])]:
            with self.assertRaises(Rejected):self.service.register(encode(data))
        for _ in range(250):
            with self.assertRaises(Rejected):self.service.register(os.urandom(32))

    def test_algorithm_and_header_confusion(self):
        cert=self.service.register(self.registration());parts=list(cbor2.loads(cert).value)
        for headers in [{1:-8,4:key_id(self.issuer).encode()},{1:-7,4:b'bad'},{1:-7,4:key_id(self.issuer).encode(),99:True}]:
            changed=parts.copy();changed[0]=encode(headers)
            with self.assertRaises(Rejected):self.result(encode(cbor2.CBORTag(18,changed)))
        changed=parts.copy();changed[1]={1:-7}
        with self.assertRaises(Rejected):self.result(encode(cbor2.CBORTag(18,changed)))

    def test_quota_and_session_retry(self):
        session=secrets.token_hex(16)
        first=self.challenge(session=session)
        for _ in range(12):self.assertEqual(self.challenge(session=session),first)
        for _ in range(9):self.challenge()
        with self.assertRaisesRegex(Rejected,'quota_exceeded'):self.challenge()
        self.now+=60;self.challenge()

    def test_signer_mismatch_and_private_key_roundtrip(self):
        other=ec.generate_private_key(ec.SECP256R1())
        with self.assertRaisesRegex(Rejected,'issuer_key_mismatch'):Service(self.root/'db.sqlite',other)
        path=self.root/'key.pem';key=create_key(path)
        self.assertEqual(public_bytes(key),public_bytes(load_key(path)))
        with self.assertRaises(FileExistsError):create_key(path)

    def test_http_end_to_end_and_bounds(self):
        server=make_server(self.service,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base=f'http://127.0.0.1:{server.server_port}'
        req=self.registration();cert=request(base,'/v1/register',req)
        self.assertEqual(self.result(cert)['content'],'exact_match')
        self.assertEqual(request(base,'/v1/records/'+unpack(cert)[0]['id']),cert)
        with self.assertRaises(Rejected):request(base,'/v1/register',b'x'*16385)
        with self.assertRaises(Rejected):request(base,'/v1/register',b'not cbor')
        for url in ['https://example.com','http://127.0.0.1.evil.test','http://user@localhost']:
            with self.assertRaises(Rejected):request(url,'/v1/records/test')
        connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
        connection.request('POST','/v1/register',body=b'{}',headers={'Content-Type':'application/json'})
        response=connection.getresponse();self.assertEqual(response.status,400);response.read();connection.close()

    def test_camera_declaration_never_becomes_attestation(self):
        cert=self.service.register(self.registration(source='camera_unverified'))
        result=self.result(cert)
        self.assertEqual(result['source_declaration'],'camera_unverified')
        self.assertEqual(result['capture_checks']['camera_origin'],'unavailable')
        self.assertEqual(result['capture_checks']['hardware_key'],'unavailable')
        self.assertEqual(result['absence_of_ai'],'not_established')

    def test_registration_quota_and_rollback(self):
        req=self.registration()
        with self.service.connect() as db:
            db.execute('INSERT INTO quotas VALUES (?,?,?,?)',(key_id(self.key),'register',self.now//86400,100))
        with self.assertRaisesRegex(Rejected,'quota_exceeded'):self.service.register(req)
        with self.service.connect() as db:
            db.execute('DELETE FROM quotas WHERE kind=?',('register',))
        self.assertEqual(self.result(self.service.register(req))['content'],'exact_match')
