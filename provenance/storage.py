"""Development key storage. Production requires a separate protected signer."""
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .protocol import Rejected, public_bytes


def private_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def create_key(path):
    key = ec.generate_private_key(ec.SECP256R1())
    private_write(path, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    return key


def load_key(path):
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    public_bytes(key)  # Restrict curve and algorithm even for local key files.
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise Rejected('invalid_private_key')
    return key
