"""Transactional, development-only registration. No attestation success is fabricated."""
import contextlib
import hashlib
import secrets
import sqlite3
import time
from pathlib import Path

from .protocol import (Rejected, decode, encode, fields, hexstr, integer, key_id, message,
                       public_key, sign, token, typed, unpack, verify)

SCHEMA = '''
CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS invitations (digest BLOB PRIMARY KEY, expires INTEGER NOT NULL, used_by TEXT);
CREATE TABLE IF NOT EXISTS installations (id TEXT PRIMARY KEY, pub BLOB NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS challenges (nonce BLOB PRIMARY KEY, owner TEXT NOT NULL, session TEXT NOT NULL,
 purpose TEXT NOT NULL, expires INTEGER NOT NULL, consumed INTEGER NOT NULL DEFAULT 0,
 UNIQUE(owner,session,purpose));
CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, owner TEXT NOT NULL, digest BLOB NOT NULL, certificate BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS tombstones (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS app_attest_keys (owner TEXT PRIMARY KEY, key_id BLOB UNIQUE NOT NULL,
 pub BLOB NOT NULL, counter INTEGER NOT NULL, policy BLOB NOT NULL, enrollment_digest BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS app_attest_blocks (owner TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS app_attest_receipts (id TEXT PRIMARY KEY, bundle_digest BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS quotas (owner TEXT NOT NULL, kind TEXT NOT NULL, bucket INTEGER NOT NULL,
 count INTEGER NOT NULL, PRIMARY KEY(owner,kind,bucket));
'''


class InvalidAttestation(Exception):
    def __init__(self, owner, reason):
        self.owner, self.reason = owner, reason
        super().__init__(reason)


class Service:
    def __init__(self, database, signer, clock=time.time, *, app_attest=None):
        self.app_attest = app_attest
        self.database, self.signer, self.clock = str(database), signer, clock
        Path(database).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with contextlib.closing(self.connect()) as db, db:
            db.executescript(SCHEMA)
            db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('issuer', key_id(signer)))
            if db.execute('SELECT value FROM metadata WHERE name=?', ('issuer',)).fetchone()[0] != key_id(signer):
                raise Rejected('issuer_key_mismatch')
            if app_attest is not None:
                policy = hashlib.sha256(encode({'config':app_attest.config,'trust_source':app_attest.trust_source})).hexdigest()
                db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('app_attest_policy', policy))
                if db.execute('SELECT value FROM metadata WHERE name=?', ('app_attest_policy',)).fetchone()[0] != policy:
                    raise Rejected('attest_policy_mismatch')
        Path(database).chmod(0o600)

    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.execute('PRAGMA synchronous=FULL')
        return db

    @contextlib.contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            db.execute('SAVEPOINT operation')
            yield db
            db.commit()
        except InvalidAttestation as exc:
            # Keep the writer lock while reverting issuance and persisting the
            # failure, so another request cannot slip in before quarantine.
            db.execute('ROLLBACK TO operation')
            db.execute('INSERT OR IGNORE INTO app_attest_blocks VALUES (?)', (exc.owner,))
            db.commit()
            raise Rejected(exc.reason) from exc
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def now(self):
        return int(self.clock())

    def invitation(self):
        secret = secrets.token_bytes(32)
        with self.transaction() as db:
            db.execute('INSERT INTO invitations VALUES (?,?,NULL)',
                       (hashlib.sha256(secret).digest(), self.now()+86400))
        return secret

    def enroll(self, envelope):
        raw = unpack(envelope)[0]
        typed(raw, 'enroll', 'public_key invitation')
        key = public_key(raw['public_key'])
        payload = verify(envelope, key, 'enroll')
        digest = hashlib.sha256(token(payload['invitation'])).digest()
        owner = key_id(key)
        with self.transaction() as db:
            invitation = db.execute('SELECT expires,used_by FROM invitations WHERE digest=?', (digest,)).fetchone()
            if invitation is None or (invitation[1] is not None and invitation[1] != owner):
                raise Rejected('invalid_invitation')
            existing = db.execute('SELECT revoked FROM installations WHERE id=?', (owner,)).fetchone()
            if existing is not None and existing[0]:
                raise Rejected('installation_revoked')
            if invitation[1] == owner and existing:
                return {'installation': owner, 'capture_assurance': 'unavailable'}
            if invitation[0] <= self.now():
                raise Rejected('invitation_expired')
            db.execute('INSERT OR IGNORE INTO installations(id,pub) VALUES (?,?)', (owner, raw['public_key']))
            db.execute('UPDATE invitations SET used_by=? WHERE digest=?', (owner, digest))
        return {'installation': owner, 'capture_assurance': 'unavailable'}

    def authenticated(self, db, envelope, purpose):
        owner = unpack(envelope)[1]
        installation = db.execute('SELECT pub,revoked FROM installations WHERE id=?', (owner,)).fetchone()
        if installation is None or installation[1]:
            raise Rejected('installation_not_admitted')
        return owner, verify(envelope, public_key(installation[0]), purpose)

    def quota(self, db, owner, kind, interval, limit):
        bucket = self.now()//interval
        db.execute('DELETE FROM quotas WHERE kind=? AND bucket<?', (kind, bucket))
        row = db.execute('SELECT count FROM quotas WHERE owner=? AND kind=? AND bucket=?', (owner, kind, bucket)).fetchone()
        if row and row[0] >= limit:
            raise Rejected('quota_exceeded')
        db.execute('INSERT INTO quotas VALUES (?,?,?,1) ON CONFLICT(owner,kind,bucket) DO UPDATE SET count=count+1',
                   (owner, kind, bucket))

    def challenge(self, envelope):
        with self.transaction() as db:
            owner, p = self.authenticated(db, envelope, 'challenge')
            typed(p, 'challenge', 'session purpose')
            session = hexstr(p['session'], 32)
            if p['purpose'] not in ('register', 'remove', 'attest'):
                raise Rejected('invalid_challenge_purpose')
            if p['purpose'] == 'attest' and self.app_attest is None:
                raise Rejected('attest_not_configured')
            db.execute('DELETE FROM challenges WHERE expires<?', (self.now()-86400,))
            old = db.execute('SELECT nonce,expires,consumed FROM challenges WHERE owner=? AND session=? AND purpose=?',
                             (owner, session, p['purpose'])).fetchone()
            if old:
                if old[1] <= self.now() or old[2]:
                    raise Rejected('session_finished')
                return {'nonce': old[0], 'expires': old[1], 'session': session, 'purpose': p['purpose']}
            self.quota(db, owner, 'challenge', 60, 10)
            nonce, expires = secrets.token_bytes(32), self.now()+300
            db.execute('INSERT INTO challenges VALUES (?,?,?,?,?,0)', (nonce, owner, session, p['purpose'], expires))
        return {'nonce': nonce, 'expires': expires, 'session': session, 'purpose': p['purpose']}

    def consume(self, db, owner, session, nonce, purpose):
        token(nonce)
        row = db.execute('SELECT owner,session,purpose,expires,consumed FROM challenges WHERE nonce=?', (nonce,)).fetchone()
        if row is None or row[:3] != (owner, session, purpose) or row[4] or row[3] <= self.now():
            raise Rejected('invalid_or_expired_challenge')
        db.execute('UPDATE challenges SET consumed=1 WHERE nonce=?', (nonce,))

    def attestation_allowed(self, db, owner):
        if db.execute('SELECT 1 FROM app_attest_blocks WHERE owner=?', (owner,)).fetchone():
            raise Rejected('attest_installation_blocked')

    def attest(self, envelope):
        if self.app_attest is None: raise Rejected('attest_not_configured')
        with self.transaction() as db:
            owner, p = self.authenticated(db, envelope, 'attest')
            self.attestation_allowed(db, owner)
            typed(p, 'attest', 'session challenge key_id attestation')
            session = hexstr(p['session'], 32); token(p['challenge']); token(p['key_id'])
            digest = hashlib.sha256(encode(p)).digest()
            previous = db.execute('SELECT enrollment_digest FROM app_attest_keys WHERE owner=?', (owner,)).fetchone()
            if previous:
                if previous[0] != digest: raise Rejected('attest_key_already_bound')
                return {'app_attest':'key_bound','assurance':'cryptographic_checks_only'}
            self.consume(db, owner, session, p['challenge'], 'attest')
            context = encode(message('attest-context', installation=owner, session=session,
                                     challenge=p['challenge'], key_id=p['key_id']))
            try:
                result = self.app_attest.attest(p['attestation'], p['key_id'], hashlib.sha256(context).digest(), self.now())
            except Rejected as exc:
                raise InvalidAttestation(owner, str(exc)) from exc
            if db.execute('SELECT 1 FROM app_attest_keys WHERE key_id=?', (p['key_id'],)).fetchone():
                raise InvalidAttestation(owner, 'attest_key_reused')
            db.execute('INSERT INTO app_attest_keys VALUES (?,?,?,?,?,?)',
                       (owner, p['key_id'], result['public_key'], 0, encode(result), digest))
        return {'app_attest':'key_bound','assurance':'cryptographic_checks_only'}

    def register(self, envelope):
        return self._register(envelope)

    def register_attested(self, bundle):
        value = decode(bundle); fields(value, 'request assertion')
        if type(value['assertion']) is not bytes or not value['assertion']: raise Rejected('attest_assertion_required')
        return self._register(value['request'], value['assertion'], hashlib.sha256(bundle).digest())

    def _register(self, envelope, assertion=None, bundle_digest=None):
        with self.transaction() as db:
            owner, p = self.authenticated(db, envelope, 'register')
            self.attestation_allowed(db, owner)
            attested_key = db.execute('SELECT pub,counter FROM app_attest_keys WHERE owner=?', (owner,)).fetchone()
            if attested_key and assertion is None: raise Rejected('attest_assertion_required')
            if assertion is not None and (attested_key is None or self.app_attest is None): raise Rejected('attest_key_not_bound')
            # No client-supplied attestation booleans, capture badges or arbitrary fields.
            typed(p, 'register', 'id file_sha256 session mode challenge source')
            identifier = hexstr(p['id'], 32)
            digest = hexstr(p['file_sha256'], 64)
            session = hexstr(p['session'], 32)
            if p['source'] not in ('import', 'camera_unverified') or p['mode'] not in ('online', 'offline'):
                raise Rejected('unsupported_claim')
            if p['mode'] == 'offline' and p['challenge'] is not None:
                raise Rejected('invalid_offline_request')
            if p['mode'] == 'online':
                token(p['challenge'])
            request_digest = hashlib.sha256(encode(p)).digest()
            if db.execute('SELECT 1 FROM tombstones WHERE id=?', (identifier,)).fetchone():
                raise Rejected('id_unavailable')
            previous = db.execute('SELECT owner,digest,certificate FROM records WHERE id=?', (identifier,)).fetchone()
            if previous:
                if previous[:2] != (owner, request_digest):
                    raise Rejected('record_conflict')
                if assertion is not None:
                    receipt = db.execute('SELECT bundle_digest FROM app_attest_receipts WHERE id=?', (identifier,)).fetchone()
                    if receipt is None or receipt[0] != bundle_digest: raise Rejected('attest_retry_conflict')
                return previous[2]  # Exact committed retry, even after challenge expiry.
            self.quota(db, owner, 'register', 86400, 100)
            if p['mode'] == 'online':
                self.consume(db, owner, session, p['challenge'], 'register')
            evidence = None
            if assertion is not None:
                if p['mode'] != 'online': raise Rejected('attest_fresh_challenge_required')
                try:
                    details = self.app_attest.assertion(assertion, attested_key[0],
                        hashlib.sha256(b'proofcam.dev.v1.app-attest.assertion\0'+envelope).digest(), attested_key[1])
                except Rejected as exc:
                    raise InvalidAttestation(owner, str(exc)) from exc
                db.execute('UPDATE app_attest_keys SET counter=? WHERE owner=?', (details['counter'], owner))
                evidence = {**{k:v for k,v in details.items() if k != 'counter'}, 'status': 'cryptographic_checks_passed' if details['trust_source']=='apple_pinned_root' else 'synthetic_test_only',
                            'scope':'registration_request'}
            certificate = message('certificate', environment='development', issuer=key_id(self.signer),
                id=identifier, file_sha256=digest, registered_at=self.now(),
                policy='development-integrity-only-v1',
                checks={'enrolled_key_signature': 'passed',
                        'fresh_registration_challenge': 'passed' if p['mode']=='online' else 'not_applicable',
                        'app_integrity': 'unavailable', 'hardware_key': 'unavailable',
                        'camera_origin': 'unavailable', 'absence_of_ai': 'not_established'},
                source_declaration=p['source'])
            if evidence is not None:
                certificate['policy'] = 'development-app-attest-v1'
                certificate['app_attest'] = evidence
            signed = sign(certificate, self.signer, 'certificate')
            db.execute('INSERT INTO records VALUES (?,?,?,?)', (identifier, owner, request_digest, signed))
            if assertion is not None:
                db.execute('INSERT INTO app_attest_receipts VALUES (?,?)', (identifier, bundle_digest))
        return signed  # Return only after durable commit.

    def lookup(self, identifier):
        hexstr(identifier, 32)
        with contextlib.closing(self.connect()) as db:
            row = db.execute('SELECT certificate FROM records WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise Rejected('record_unavailable')
        return row[0]

    def remove(self, envelope):
        with self.transaction() as db:
            owner, p = self.authenticated(db, envelope, 'remove')
            typed(p, 'remove', 'id session challenge')
            identifier, session = hexstr(p['id'], 32), hexstr(p['session'], 32)
            row = db.execute('SELECT owner FROM records WHERE id=?', (identifier,)).fetchone()
            if row is None or row[0] != owner:
                raise Rejected('record_unavailable')
            self.consume(db, owner, session, p['challenge'], 'remove')
            db.execute('DELETE FROM records WHERE id=?', (identifier,))
            db.execute('DELETE FROM app_attest_receipts WHERE id=?', (identifier,))
            db.execute('INSERT INTO tombstones VALUES (?)', (identifier,))
        return {'availability': 'removed'}

    def revoke(self, owner):
        hexstr(owner, 64)
        with self.transaction() as db:
            db.execute('UPDATE installations SET revoked=1 WHERE id=?', (owner,))
