"""Independent, offline verification; certificate contents never select trust or URLs."""
import hashlib
import time
from pathlib import Path

from .protocol import (Rejected, fields, hexstr, integer, key_id, public_bytes, public_key,
                       typed, unpack, verify)

MAX_FILE = 25 * 1024 * 1024


def file_hash(path):
    digest, total = hashlib.sha256(), 0
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024*1024):
            total += len(chunk)
            if total > MAX_FILE:
                raise Rejected('file_too_large')
            digest.update(chunk)
    if not total:
        raise Rejected('empty_file')
    return digest.hexdigest()


def development_trust(key, now=None):
    now = int(time.time()) if now is None else now
    return {'version': 1, 'environment': 'development', 'valid_from': now, 'valid_until': now+86400,
            'keys': {key_id(key): {'public_key': public_bytes(key), 'status': 'active'}}}


def verify_file(certificate, path, trust, *, allow_development=False, expected_id=None, now=None):
    now = int(time.time()) if now is None else now
    fields(trust, 'version environment valid_from valid_until keys')
    if type(trust['version']) is not int or trust['version'] != 1 or trust['environment'] != 'development':
        raise Rejected('unsupported_trust_policy')
    if not allow_development:
        raise Rejected('development_issuer_rejected')
    valid_from, valid_until = integer(trust['valid_from']), integer(trust['valid_until'])
    if not valid_from <= now < valid_until:
        raise Rejected('stale_or_future_trust')
    if type(trust['keys']) is not dict:
        raise Rejected('invalid_trust_store')
    _, kid, *_ = unpack(certificate)
    entry = trust['keys'].get(kid)
    if entry is None:
        raise Rejected('unknown_issuer')
    fields(entry, 'public_key status')
    if entry['status'] != 'active':
        raise Rejected('issuer_not_active')
    payload = verify(certificate, public_key(entry['public_key']), 'certificate')
    typed(payload, 'certificate', 'environment issuer id file_sha256 registered_at policy checks source_declaration')
    identifier = hexstr(payload['id'], 32)
    digest = hexstr(payload['file_sha256'], 64)
    if expected_id is not None and identifier != hexstr(expected_id, 32):
        raise Rejected('record_id_mismatch')
    if payload['issuer'] != kid or payload['environment'] != 'development' or payload['policy'] != 'development-integrity-only-v1':
        raise Rejected('unsupported_certificate_policy')
    if integer(payload['registered_at']) > now:
        raise Rejected('future_registration')
    if payload['source_declaration'] not in ('import', 'camera_unverified'):
        raise Rejected('unsupported_source')
    checks = payload['checks']
    fields(checks, 'enrolled_key_signature fresh_registration_challenge app_integrity hardware_key camera_origin absence_of_ai')
    required = {'enrolled_key_signature':'passed', 'app_integrity':'unavailable', 'hardware_key':'unavailable',
                'camera_origin':'unavailable', 'absence_of_ai':'not_established'}
    if any(checks[k] != v for k,v in required.items()) or checks['fresh_registration_challenge'] not in ('passed','not_applicable'):
        raise Rejected('unsupported_assurance_claim')
    return {'record_id': identifier, 'signature': 'valid', 'issuer': 'development_only',
            'content': 'exact_match' if file_hash(path)==digest else 'different_bytes',
            'capture_checks': checks, 'source_declaration': payload['source_declaration'],
            'availability': 'not_checked_offline', 'production_authenticity': 'not_established',
            'absence_of_ai': 'not_established'}
