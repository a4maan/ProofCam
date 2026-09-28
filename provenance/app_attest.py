"""Bounded iOS App Attest cryptographic validation, with explicit policy and trust scope.

Apple receipt/fraud-metric assessment and sensor provenance are outside this validator.
"""
import hashlib
import io
import re
from datetime import datetime, timezone
from pathlib import Path

import cbor2
from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtensionOID, ObjectIdentifier

from .protocol import Rejected, bounded_structure, fields, integer, public_bytes, public_key

ROOT_SHA256 = '1cb9823ba28ba6ad2d33a006941de2ae4f513ef1d4e831b9f7e0fa7b6242c932'
NONCE_OID = ObjectIdentifier('1.2.840.113635.100.8.2')
ATTEST_EKU = ObjectIdentifier('1.2.840.113635.100.4.24')


def apple_cbor(data):
    """Apple map ordering need not match our canonical request encoding."""
    if type(data) is not bytes or not 0 < len(data) <= 16_384:
        raise Rejected('attest_message_size')
    bounded_structure(data)
    try:
        stream = io.BytesIO(data)
        value = cbor2.CBORDecoder(stream, max_depth=16, allow_indefinite=False,
                                 allow_duplicate_keys=False).decode()
        if stream.read(1):
            raise Rejected('attest_trailing_data')
        return value
    except (cbor2.CBORError, ValueError, TypeError, OverflowError) as exc:
        raise Rejected('attest_invalid_cbor') from exc


def split_cbor(data):
    # The supported P-256 COSE key profile is exactly 77 bytes. Bound the slice
    # before decoding, so attacker-supplied container lengths cannot allocate.
    if not 77 < len(data) <= 1024:
        raise Rejected('attest_invalid_cose_key')
    return apple_cbor(data[:77]), data[77:]


class AppAttestValidator:
    def __init__(self, config, *, _test_root=None):
        fields(config, 'app_id environment bundle_versions validation_categories')
        app_id = config['app_id']
        if type(app_id) is not str or re.fullmatch(r'[A-Z0-9]{10}\.[A-Za-z0-9][A-Za-z0-9.-]{1,180}', app_id) is None:
            raise Rejected('attest_invalid_app_id')
        if config['environment'] not in ('development', 'production'):
            raise Rejected('attest_invalid_environment')
        versions, categories = config['bundle_versions'], config['validation_categories']
        if type(versions) is not list or not 1 <= len(versions) <= 16 or any(type(v) is not str or not 1 <= len(v) <= 64 for v in versions):
            raise Rejected('attest_invalid_versions')
        if type(categories) is not list or not categories or any(type(v) is not int or v not in (2, 3, 4, 5) for v in categories):
            raise Rejected('attest_invalid_categories')
        if config['environment'] == 'development' and categories != [3]:
            raise Rejected('attest_development_category_required')
        if config['environment'] == 'production' and 3 in categories:
            raise Rejected('attest_production_category_required')
        self.config = config
        self.root = _test_root or x509.load_pem_x509_certificate((Path(__file__).parent/'trust/apple-app-attestation-root.pem').read_bytes())
        self.trust_source = 'apple_pinned_root' if self.root.fingerprint(hashes.SHA256()).hex() == ROOT_SHA256 else 'synthetic_test_only'
        if _test_root is None and self.trust_source != 'apple_pinned_root':
            raise Rejected('attest_root_pin_mismatch')
        self.rp_hash = hashlib.sha256(app_id.encode()).digest()

    def policy(self):
        return {'app_id': self.config['app_id'], 'environment': self.config['environment'],
                'trust_source': self.trust_source}

    def extensions(self, raw):
        extensions = apple_cbor(raw)
        if type(extensions) is not dict:
            raise Rejected('attest_extensions_required')
        # Both spellings are described in Apple's attestation/assertion guidance.
        if set(extensions) == {'apple_bundle_version_01', 'apple_validation_category_01'}:
            version = extensions['apple_bundle_version_01']
            category = extensions['apple_validation_category_01']
        elif set(extensions) == {'bundleVersion', 'validationCategory'}:
            version, category = extensions['bundleVersion'], extensions['validationCategory']
        else:
            raise Rejected('attest_unknown_extensions')
        if type(category) is bytes and len(category) == 4:
            category = int.from_bytes(category, 'little')
        if type(category) is not int or category not in self.config['validation_categories']:
            raise Rejected('attest_disallowed_validation_category')
        if type(version) is not str or version not in self.config['bundle_versions']:
            raise Rejected('attest_disallowed_build')
        return {'bundle_version': version, 'validation_category': category}

    def auth_prefix(self, data, *, attestation):
        if type(data) is not bytes or not 37 <= len(data) <= 1024:
            raise Rejected('attest_authdata_size')
        if data[:32] != self.rp_hash:
            raise Rejected('attest_wrong_app')
        flags = data[32]
        # App Attest has no user-presence/user-verification semantics. Require the
        # extensions bit, and the attested-credential bit only at key enrollment.
        if flags != (0xc0 if attestation else 0x80):
            raise Rejected('attest_unsupported_flags_or_missing_extensions')
        return int.from_bytes(data[33:37], 'big')

    def chain(self, chain, now):
        if type(chain) is not list or len(chain) != 2 or any(type(c) is not bytes or not 0 < len(c) <= 8192 for c in chain):
            raise Rejected('attest_invalid_chain')
        try:
            leaf, intermediate = [x509.load_der_x509_certificate(c) for c in chain]
            certificates = [leaf, intermediate, self.root]
            instant = datetime.fromtimestamp(now, timezone.utc)
            for index, cert in enumerate(certificates):
                if not cert.not_valid_before_utc <= instant <= cert.not_valid_after_utc:
                    raise Rejected('attest_certificate_expired')
                if cert.signature_hash_algorithm is None or cert.signature_hash_algorithm.name not in ('sha256', 'sha384', 'sha512'):
                    raise Rejected('attest_weak_certificate_signature')
                bc = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
                usage = cert.extensions.get_extension_for_class(x509.KeyUsage).value
                if bc.ca != (index > 0) or (index > 0 and not usage.key_cert_sign) or (index == 0 and (not usage.digital_signature or usage.key_cert_sign)):
                    raise Rejected('attest_invalid_certificate_constraints')
                if index > 0 and bc.path_length is not None and bc.path_length < index-1:
                    raise Rejected('attest_invalid_path_length')
                for extension in cert.extensions:
                    if extension.critical and extension.oid not in (ExtensionOID.BASIC_CONSTRAINTS, ExtensionOID.KEY_USAGE, ExtensionOID.EXTENDED_KEY_USAGE):
                        raise Rejected('attest_unknown_critical_extension')
                if index > 0:
                    try:
                        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
                        if ATTEST_EKU not in eku: raise Rejected('attest_invalid_issuer_eku')
                    except x509.ExtensionNotFound:
                        pass
            eku = leaf.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
            if list(eku) != [ATTEST_EKU]:
                raise Rejected('attest_invalid_leaf_eku')
            leaf.verify_directly_issued_by(intermediate)
            intermediate.verify_directly_issued_by(self.root)
            self.root.verify_directly_issued_by(self.root)
            public_bytes(leaf.public_key())  # Require a P-256 credential key.
            return leaf
        except (ValueError, TypeError, InvalidSignature, UnsupportedAlgorithm, x509.ExtensionNotFound, x509.DuplicateExtension) as exc:
            raise Rejected('attest_invalid_certificate_chain') from exc

    def attest(self, blob, key_identifier, client_data_hash, now):
        if type(key_identifier) is not bytes or len(key_identifier) != 32 or type(client_data_hash) is not bytes or len(client_data_hash) != 32:
            raise Rejected('attest_invalid_binding')
        obj = apple_cbor(blob)
        fields(obj, 'fmt attStmt authData')
        if obj['fmt'] != 'apple-appattest': raise Rejected('attest_wrong_format')
        statement = obj['attStmt']; fields(statement, 'x5c receipt')
        if type(statement['receipt']) is not bytes or not 0 < len(statement['receipt']) <= 8192:
            raise Rejected('attest_invalid_receipt')
        leaf = self.chain(statement['x5c'], now)
        data = obj['authData']
        if self.auth_prefix(data, attestation=True) != 0: raise Rejected('attest_initial_counter')
        aaguid = b'appattestdevelop' if self.config['environment']=='development' else b'appattest'+b'\0'*7
        if data[37:53] != aaguid: raise Rejected('attest_wrong_environment')
        if data[53:55] != b'\x00\x20' or data[55:87] != key_identifier:
            raise Rejected('attest_wrong_credential_id')
        pub = public_bytes(leaf.public_key())
        if hashlib.sha256(pub).digest() != key_identifier: raise Rejected('attest_wrong_key_identifier')
        cose, rest = split_cbor(data[87:])
        expected = {1: 2, 3: -7, -1: 1, -2: pub[1:33], -3: pub[33:]}
        if cose != expected: raise Rejected('attest_cose_key_mismatch')
        details = self.extensions(rest)
        nonce = hashlib.sha256(data+client_data_hash).digest()
        try:
            extension = leaf.extensions.get_extension_for_oid(NONCE_OID).value
            # SEQUENCE { [1] EXPLICIT OCTET STRING(32) }; fixed DER lengths.
            if not isinstance(extension, x509.UnrecognizedExtension) or extension.value != b'\x30\x24\xa1\x22\x04\x20'+nonce:
                raise Rejected('attest_nonce_mismatch')
        except x509.ExtensionNotFound as exc:
            raise Rejected('attest_nonce_missing') from exc
        return {'public_key': pub, 'counter': 0, **self.policy(), **details,
                'receipt_sha256': hashlib.sha256(statement['receipt']).hexdigest(),
                'receipt_assessment': 'not_performed'}

    def assertion(self, blob, pub, client_data_hash, previous_counter):
        obj = apple_cbor(blob); fields(obj, 'signature authenticatorData')
        signature, data = obj['signature'], obj['authenticatorData']
        if type(signature) is not bytes or not 8 <= len(signature) <= 80:
            raise Rejected('attest_invalid_assertion_signature')
        counter = self.auth_prefix(data, attestation=False)
        if counter <= integer(previous_counter, 0, 0xffffffff): raise Rejected('attest_counter_replay')
        if type(client_data_hash) is not bytes or len(client_data_hash) != 32:
            raise Rejected('attest_invalid_binding')
        details = self.extensions(data[37:])
        try:
            public_key(pub).verify(signature, data+client_data_hash, ec.ECDSA(hashes.SHA256()))
        except (InvalidSignature, ValueError) as exc:
            raise Rejected('attest_invalid_assertion_signature') from exc
        return {'counter': counter, **self.policy(), **details, 'receipt_assessment': 'not_performed'}
