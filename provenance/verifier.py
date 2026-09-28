"""Independent, offline verification; certificate contents never select trust or URLs."""
import hashlib
import time
from .storage import regular_reader

from .protocol import (Rejected, fields, hexstr, integer, key_id, public_bytes, public_key,
                       typed, unpack, verify)

MAX_FILE = 25 * 1024 * 1024


def file_hash(path):
    digest, total = hashlib.sha256(), 0
    with regular_reader(path) as stream:
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
    attested = payload.get('policy') == 'development-app-attest-v1' if type(payload) is dict else False
    typed(payload, 'certificate', 'environment issuer id file_sha256 registered_at policy checks source_declaration' + (' app_attest' if attested else ''))
    identifier = hexstr(payload['id'], 32)
    digest = hexstr(payload['file_sha256'], 64)
    if expected_id is not None and identifier != hexstr(expected_id, 32):
        raise Rejected('record_id_mismatch')
    if payload['issuer'] != kid or payload['environment'] != 'development' or payload['policy'] not in ('development-integrity-only-v1','development-app-attest-v1'):
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
    app_attest = None
    if attested:
        app_attest = payload['app_attest']
        fields(app_attest, 'app_id environment trust_source bundle_version validation_category receipt_assessment status scope')
        import re
        if type(app_attest['app_id']) is not str or re.fullmatch(r'[A-Z0-9]{10}\.[A-Za-z0-9][A-Za-z0-9.-]{1,180}', app_attest['app_id']) is None:
            raise Rejected('unsupported_attest_identity')
        integer(app_attest['validation_category'],2,5)
        if app_attest['environment'] not in ('development','production') or type(app_attest['bundle_version']) is not str or not 1 <= len(app_attest['bundle_version']) <= 64:
            raise Rejected('unsupported_attest_policy')
        if type(app_attest['trust_source']) is not str: raise Rejected('unsupported_attest_claim')
        expected_status = {'apple_pinned_root':'cryptographic_checks_passed','synthetic_test_only':'synthetic_test_only'}.get(app_attest['trust_source'])
        if expected_status is None or app_attest['status'] != expected_status or app_attest['scope'] != 'registration_request' or app_attest['receipt_assessment'] != 'not_performed':
            raise Rejected('unsupported_attest_claim')
        if checks['fresh_registration_challenge'] != 'passed': raise Rejected('unsupported_attest_freshness')
    return {'record_id': identifier, 'signature': 'valid', 'issuer': 'development_only',
            'content': 'exact_match' if file_hash(path)==digest else 'different_bytes',
            'capture_checks': checks, 'app_attest': app_attest, 'source_declaration': payload['source_declaration'],
            'availability': 'not_checked_offline', 'production_authenticity': 'not_established',
            'absence_of_ai': 'not_established'}
