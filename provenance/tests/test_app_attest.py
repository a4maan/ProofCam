"""Synthetic PKI tests; never label these as real Apple/device evidence."""
import concurrent.futures
import contextlib
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import tempfile
import unittest

import cbor2
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from provenance.app_attest import AppAttestValidator, NONCE_OID, ATTEST_EKU, ROOT_SHA256, apple_cbor
from provenance.protocol import Rejected, encode, key_id, message, public_bytes, sign, unpack
from provenance.service import Service
from provenance.verifier import development_trust, verify_file


class AppAttestTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.now=1800000000
        self.root_key=ec.generate_private_key(ec.SECP384R1())
        self.intermediate_key=ec.generate_private_key(ec.SECP384R1())
        self.attest_key=ec.generate_private_key(ec.SECP256R1())
        self.device=ec.generate_private_key(ec.SECP256R1());self.issuer=ec.generate_private_key(ec.SECP256R1())
        self.root=self.certificate('test root',self.root_key,self.root_key,None,True,1)
        self.intermediate=self.certificate('test intermediate',self.intermediate_key,self.root_key,self.root,True,0)
        self.config={'app_id':'TESTTEAM01.com.a4maan.proofcam.research','environment':'development','bundle_versions':['1'],'validation_categories':[3]}
        self.validator=AppAttestValidator(self.config,_test_root=self.root)
        self.service=Service(self.folder/'db',self.issuer,lambda:self.now,app_attest=self.validator)
        self.enroll(self.device)
        self.file=self.folder/'photo.jpg';self.file.write_bytes(b'final test image bytes')

    def certificate(self,name,key,issuer_key,issuer,ca,path_length,nonce=None,expired=False):
        subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,name)])
        now=datetime.fromtimestamp(self.now,timezone.utc)
        b=x509.CertificateBuilder().subject_name(subject).issuer_name(issuer.subject if issuer else subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
        b=b.not_valid_before(now-timedelta(days=2)).not_valid_after(now+timedelta(days=-1 if expired else 2))
        b=b.add_extension(x509.BasicConstraints(ca=ca,path_length=path_length),critical=True)
        b=b.add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=False,data_encipherment=False,key_agreement=False,key_cert_sign=ca,crl_sign=ca,encipher_only=None,decipher_only=None),critical=True)
        if not ca:
            b=b.add_extension(x509.ExtendedKeyUsage([ATTEST_EKU]),critical=False)
            b=b.add_extension(x509.UnrecognizedExtension(NONCE_OID,b'\x30\x24\xa1\x22\x04\x20'+nonce),critical=False)
        return b.sign(issuer_key,hashes.SHA384())

    def enroll(self,key):
        self.service.enroll(sign(message('enroll',public_key=public_bytes(key),invitation=self.service.invitation()),key,'enroll'))

    def challenge(self,purpose='attest',key=None):
        return self.service.challenge(sign(message('challenge',session=os.urandom(16).hex(),purpose=purpose),key or self.device,'challenge'))

    def extensions(self,version='1',category=3):
        return encode({'apple_bundle_version_01':version,'apple_validation_category_01':category.to_bytes(4,'little')})

    def attestation(self,client_hash,*,app_hash=None,aaguid=None,version='1',category=3,expired=False,nonce=None):
        pub=public_bytes(self.attest_key);kid=hashlib.sha256(pub).digest()
        cose=encode({1:2,3:-7,-1:1,-2:pub[1:33],-3:pub[33:]})
        self.assertEqual(len(cose),77)
        data=(app_hash or self.validator.rp_hash)+b'\xc0'+b'\0'*4+(aaguid or b'appattestdevelop')+b'\x00\x20'+kid+cose+self.extensions(version,category)
        leaf=self.certificate('credential',self.attest_key,self.intermediate_key,self.intermediate,False,None,
                              nonce or hashlib.sha256(data+client_hash).digest(),expired)
        return encode({'fmt':'apple-appattest','authData':data,'attStmt':{'x5c':[leaf.public_bytes(serialization.Encoding.DER),self.intermediate.public_bytes(serialization.Encoding.DER)],'receipt':b'synthetic receipt; not Apple assessed'}}),kid

    def attestation_request(self,key=None,**changes):
        key=key or self.device;ch=self.challenge(key=key)
        kid=hashlib.sha256(public_bytes(self.attest_key)).digest()
        context=encode(message('attest-context',installation=key_id(key),session=ch['session'],challenge=ch['nonce'],key_id=kid))
        blob,_=self.attestation(hashlib.sha256(context).digest(),**changes)
        return sign(message('attest',session=ch['session'],challenge=ch['nonce'],key_id=kid,attestation=blob),key,'attest')

    def registration(self):
        ch=self.challenge('register')
        return sign(message('register',id=os.urandom(16).hex(),file_sha256=hashlib.sha256(self.file.read_bytes()).hexdigest(),session=ch['session'],challenge=ch['nonce'],mode='online',source='camera_unverified'),self.device,'register')

    def assertion(self,request,counter=1,version='1',category=3):
        data=self.validator.rp_hash+b'\x80'+counter.to_bytes(4,'big')+self.extensions(version,category)
        client_hash=hashlib.sha256(b'proofcam.dev.v1.app-attest.assertion\0'+request).digest()
        signature=self.attest_key.sign(data+client_hash,ec.ECDSA(hashes.SHA256()))
        return encode({'signature':signature,'authenticatorData':data})

    def bundle(self,request,counter=1,**changes):
        return encode({'request':request,'assertion':self.assertion(request,counter,**changes)})

    def test_valid_synthetic_attestation_and_bound_assertion(self):
        enrollment=self.attestation_request();self.service.attest(enrollment)
        self.assertEqual(self.service.attest(enrollment)['app_attest'],'key_bound')
        req=self.registration();bundle=self.bundle(req)
        cert=self.service.register_attested(bundle)
        self.assertEqual(self.service.register_attested(bundle),cert)
        result=verify_file(cert,self.file,development_trust(self.issuer,self.now),allow_development=True,now=self.now)
        self.assertEqual(result['content'],'exact_match')
        self.assertEqual(result['app_attest']['status'],'synthetic_test_only')
        self.assertEqual(result['capture_checks']['app_integrity'],'unavailable')
        self.assertEqual(result['absence_of_ai'],'not_established')
        restart=Service(self.folder/'db',self.issuer,lambda:self.now,app_attest=self.validator)
        self.assertEqual(restart.register_attested(bundle),cert)

    def test_trust_root_pinned_and_unknown_chain_rejected(self):
        validator=AppAttestValidator(self.config)
        self.assertEqual(validator.root.fingerprint(hashes.SHA256()).hex(),ROOT_SHA256)
        blob,kid=self.attestation(b'0'*32)
        with self.assertRaises(Rejected):validator.attest(blob,kid,b'0'*32,self.now)

    def test_nonce_environment_identity_build_and_category(self):
        for changes in [dict(nonce=b'x'*32),dict(aaguid=b'appattest'+b'\0'*7),dict(app_hash=b'x'*32),dict(version='evil'),dict(category=10),dict(expired=True)]:
            blob,kid=self.attestation(b'0'*32,**changes)
            with self.subTest(changes=changes),self.assertRaises(Rejected):self.validator.attest(blob,kid,b'0'*32,self.now)
        blob,kid=self.attestation(b'0'*32)
        with self.assertRaises(Rejected):self.validator.attest(blob,b'1'*32,b'0'*32,self.now)

    def test_forged_or_failed_evidence_blocks_basic_downgrade(self):
        bad=self.attestation_request(nonce=b'x'*32)
        with self.assertRaisesRegex(Rejected,'attest_nonce_mismatch'):self.service.attest(bad)
        req=self.registration()
        with self.assertRaisesRegex(Rejected,'attest_installation_blocked'):self.service.register(req)
        with contextlib.closing(self.service.connect()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM app_attest_keys').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM app_attest_blocks').fetchone()[0],1)
            self.assertEqual(db.execute("SELECT consumed FROM challenges WHERE purpose='attest'").fetchone()[0],0)

    def test_bound_installation_cannot_omit_assertion_even_without_config(self):
        self.service.attest(self.attestation_request());req=self.registration()
        for service in [self.service,Service(self.folder/'db',self.issuer,lambda:self.now)]:
            with self.assertRaisesRegex(Rejected,'attest_assertion_required'):service.register(req)

    def test_assertion_cannot_move_to_another_request(self):
        self.service.attest(self.attestation_request());first=self.registration();second=self.registration()
        with self.assertRaisesRegex(Rejected,'attest_invalid_assertion_signature'):
            self.service.register_attested(encode({'request':second,'assertion':self.assertion(first)}))
        with self.assertRaisesRegex(Rejected,'attest_installation_blocked'):self.service.register_attested(self.bundle(second))

    def test_counter_replay_and_concurrent_identical_retry(self):
        self.service.attest(self.attestation_request());req=self.registration();bundle=self.bundle(req,5)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(self.service.register_attested,[bundle]*4))
        self.assertEqual(len(set(results)),1)
        with self.assertRaisesRegex(Rejected,'attest_counter_replay'):
            self.service.register_attested(self.bundle(self.registration(),5))

    def test_expired_challenge_and_assertion_build_policy(self):
        self.service.attest(self.attestation_request());req=self.registration();bundle=self.bundle(req)
        self.now+=300
        with self.assertRaisesRegex(Rejected,'invalid_or_expired_challenge'):self.service.register_attested(bundle)
        new=self.registration()
        with self.assertRaisesRegex(Rejected,'attest_disallowed_build'):self.service.register_attested(self.bundle(new,version='evil'))

    def test_storage_failure_rolls_back_counter_and_challenge(self):
        self.service.attest(self.attestation_request());req=self.registration();bundle=self.bundle(req)
        with contextlib.closing(self.service.connect()) as db,db:
            db.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON records BEGIN SELECT RAISE(ABORT,'test'); END")
        import sqlite3
        with self.assertRaises(sqlite3.Error):self.service.register_attested(bundle)
        with contextlib.closing(self.service.connect()) as db,db:
            self.assertEqual(db.execute('SELECT counter FROM app_attest_keys').fetchone()[0],0)
            db.execute('DROP TRIGGER fail_insert')
        self.service.register_attested(bundle)

    def test_second_owner_cannot_bind_same_attest_key(self):
        self.service.attest(self.attestation_request());other=ec.generate_private_key(ec.SECP256R1());self.enroll(other)
        with self.assertRaisesRegex(Rejected,'attest_key_reused'):self.service.attest(self.attestation_request(other))

    def test_policy_cannot_change_silently(self):
        changed=dict(self.config,bundle_versions=['2'])
        with self.assertRaisesRegex(Rejected,'attest_policy_mismatch'):
            Service(self.folder/'db',self.issuer,app_attest=AppAttestValidator(changed,_test_root=self.root))

    def test_malformed_apple_cbor_and_missing_extensions(self):
        for raw in [b'',b'\xa2\x61a\x01\x61a\x02',b'\x9b'+b'\xff'*8,b'\x81'*1000,b'x'*16385]:
            with self.assertRaises(Rejected):apple_cbor(raw)
        blob,kid=self.attestation(b'0'*32);obj=cbor2.loads(blob)
        for mutate in [lambda d:d.update(fmt='none'),lambda d:d.update(authData=b'x'),lambda d:d['attStmt'].update(x5c=[]),lambda d:d['attStmt'].update(receipt=b'')]:
            import copy
            value=copy.deepcopy(obj);mutate(value)
            with self.assertRaises(Rejected):self.validator.attest(encode(value),kid,b'0'*32,self.now)
        raw=bytearray(obj['authData']);raw[32]=0x40
        with self.assertRaises(Rejected):self.validator.attest(encode(dict(obj,authData=bytes(raw))),kid,b'0'*32,self.now)

    def test_credential_counter_cose_and_certificate_corruption(self):
        blob,kid=self.attestation(b'0'*32);obj=cbor2.loads(blob)
        import copy
        for offset in [36,55,90]:
            value=copy.deepcopy(obj);data=bytearray(value['authData']);data[offset]^=1;value['authData']=bytes(data)
            with self.assertRaises(Rejected):self.validator.attest(encode(value),kid,b'0'*32,self.now)
        value=copy.deepcopy(obj);leaf=bytearray(value['attStmt']['x5c'][0]);leaf[-1]^=1;value['attStmt']['x5c'][0]=bytes(leaf)
        with self.assertRaises(Rejected):self.validator.attest(encode(value),kid,b'0'*32,self.now)

    def test_assertion_identity_flags_signature_and_missing_extensions(self):
        request=b'exact signed request';blob=self.assertion(request)
        client_hash=hashlib.sha256(b'proofcam.dev.v1.app-attest.assertion\0'+request).digest()
        obj=cbor2.loads(blob)
        for offset in [0,32]:
            data=bytearray(obj['authenticatorData']);data[offset]^=1
            with self.assertRaises(Rejected):self.validator.assertion(encode(dict(obj,authenticatorData=bytes(data))),public_bytes(self.attest_key),client_hash,0)
        with self.assertRaises(Rejected):self.validator.assertion(encode(dict(obj,signature=b'0'*70)),public_bytes(self.attest_key),client_hash,0)
        with self.assertRaises(Rejected):self.validator.assertion(encode(dict(obj,authenticatorData=obj['authenticatorData'][:37])),public_bytes(self.attest_key),client_hash,0)

    def test_http_attestation_and_challenge_json_handoff(self):
        import threading,subprocess,sys,json
        from provenance.http_server import make_server
        from provenance.__main__ import request
        server=make_server(self.service,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        url=f'http://127.0.0.1:{server.server_port}'
        result=request(url,'/v1/attest',self.attestation_request())
        self.assertEqual(cbor2.loads(result)['app_attest'],'key_bound')
        req=self.registration();certificate=request(url,'/v1/register-attested',self.bundle(req))
        self.assertEqual(unpack(certificate)[0]['policy'],'development-app-attest-v1')
        challenge=self.challenge();path=self.folder/'challenge.cbor';path.write_bytes(encode(challenge))
        result=subprocess.run([sys.executable,'-m','provenance','challenge-json','--input',str(path),'--out',str(self.folder/'challenge.json')],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads((self.folder/'challenge.json').read_text())
        self.assertEqual(value['session'],challenge['session'])
        import base64
        self.assertEqual(base64.b64decode(value['nonce']),challenge['nonce'])
