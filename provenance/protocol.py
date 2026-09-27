"""Strict deterministic CBOR and COSE_Sign1 ES256 for development protocol v1."""
import hashlib
import io
import re

import cbor2
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

MAX_MESSAGE = 16_384
PREFIX = 'proofcam.dev.v1.'


class Rejected(ValueError):
    """A public, non-sensitive reason code; never include supplied values."""


def encode(value):
    return cbor2.dumps(value, canonical=True)


def bounded_structure(data):
    """Reject expensive CBOR structures before the library allocates containers."""
    position, nodes = 0, 0
    def item(depth):
        nonlocal position, nodes
        nodes += 1
        if depth > 16 or nodes > 512 or position >= len(data):
            raise Rejected('cbor_structure_limit')
        first = data[position]; position += 1
        major, additional = first >> 5, first & 31
        if major == 7:
            if first != 0xf6:
                raise Rejected('unsupported_cbor_simple')
            return
        if additional < 24:
            value = additional
        elif additional in (24, 25, 26, 27):
            size = 1 << (additional - 24)
            if position + size > len(data):
                raise Rejected('truncated_cbor')
            value = int.from_bytes(data[position:position+size], 'big'); position += size
        else:
            raise Rejected('indefinite_cbor_rejected')
        if major in (0, 1):
            return
        if major in (2, 3):
            if value > len(data) - position:
                raise Rejected('truncated_cbor')
            position += value
        elif major in (4, 5):
            if value > 64:
                raise Rejected('cbor_container_limit')
            for _ in range(value * (2 if major == 5 else 1)):
                item(depth+1)
        elif major == 6 and value == 18:
            item(depth+1)
        else:
            raise Rejected('unsupported_cbor_tag')
    item(0)
    if position != len(data):
        raise Rejected('trailing_cbor')


def decode(data):
    if type(data) is not bytes or not 0 < len(data) <= MAX_MESSAGE:
        raise Rejected('invalid_message_size')
    bounded_structure(data)
    try:
        stream = io.BytesIO(data)
        value = cbor2.CBORDecoder(stream).decode()
        # Reject duplicates, indefinite encodings, trailing data and noncanonical maps.
        if stream.read(1) or encode(value) != data:
            raise Rejected('noncanonical_cbor')
        return value
    except (cbor2.CBORError, ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise Rejected('invalid_cbor') from exc


def fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise Rejected('invalid_fields')


def integer(value, low=0, high=2**53-1):
    if type(value) is not int or not low <= value <= high:
        raise Rejected('invalid_integer')
    return value


def hexstr(value, length):
    if type(value) is not str or re.fullmatch('[0-9a-f]{'+str(length)+'}', value) is None:
        raise Rejected('invalid_identifier')
    return value


def token(value):
    if type(value) is not bytes or len(value) != 32:
        raise Rejected('invalid_token')
    return value


def public_bytes(key):
    if isinstance(key, ec.EllipticCurvePrivateKey):
        key = key.public_key()
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
        raise Rejected('unsupported_key')
    return key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def public_key(data):
    if type(data) is not bytes or len(data) != 65 or data[0] != 4:
        raise Rejected('invalid_public_key')
    try:
        return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), data)
    except ValueError as exc:
        raise Rejected('invalid_public_key') from exc


def key_id(key):
    return hashlib.sha256(public_bytes(key)).hexdigest()


def sign(payload, key, purpose):
    protected = encode({1: -7, 4: key_id(key).encode('ascii')})
    content = encode(payload)
    message = encode(['Signature1', protected, (PREFIX+purpose).encode('ascii'), content])
    r, s = utils.decode_dss_signature(key.sign(message, ec.ECDSA(hashes.SHA256())))
    return encode(cbor2.CBORTag(18, [protected, {}, content, r.to_bytes(32, 'big')+s.to_bytes(32, 'big')]))


def unpack(envelope):
    value = decode(envelope)
    if not isinstance(value, cbor2.CBORTag) or value.tag != 18:
        raise Rejected('invalid_cose')
    parts = value.value
    if not isinstance(parts, (list, tuple)) or len(parts) != 4:
        raise Rejected('invalid_cose')
    protected, unprotected, payload, signature = parts
    if unprotected != {} or type(signature) is not bytes or len(signature) != 64:
        raise Rejected('invalid_cose')
    headers = decode(protected)
    if type(headers) is not dict or set(headers) != {1, 4} or type(headers[1]) is not int or headers[1] != -7:
        raise Rejected('unsupported_headers')
    if type(headers[4]) is not bytes:
        raise Rejected('invalid_key_id')
    try:
        kid = hexstr(headers[4].decode('ascii'), 64)
    except UnicodeError as exc:
        raise Rejected('invalid_key_id') from exc
    return decode(payload), kid, protected, payload, signature


def verify(envelope, key, purpose):
    payload, kid, protected, content, signature = unpack(envelope)
    if kid != key_id(key):
        raise Rejected('wrong_key')
    r, s = int.from_bytes(signature[:32], 'big'), int.from_bytes(signature[32:], 'big')
    message = encode(['Signature1', protected, (PREFIX+purpose).encode('ascii'), content])
    try:
        key.verify(utils.encode_dss_signature(r, s), message, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError) as exc:
        raise Rejected('invalid_signature') from exc
    return payload


def typed(payload, kind, names):
    fields(payload, 'type version '+names)
    if payload['type'] != PREFIX+kind or type(payload['version']) is not int or payload['version'] != 1:
        raise Rejected('unsupported_protocol')


def message(kind, **values):
    return dict(type=PREFIX+kind, version=1, **values)
