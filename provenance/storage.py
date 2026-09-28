"""Development key storage. Production requires a separate protected signer."""
import os
import contextlib
import stat
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .protocol import Rejected, public_bytes


@contextlib.contextmanager
def regular_reader(path):
    """Open without waiting for a pipe writer, then check the actual opened object."""
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Rejected('regular_file_required')
        stream = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise
    with stream:
        yield stream


def private_write(path, data):
    """Publish only a completely written, fsynced file, without replacing an export."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.'+path.name+'.', suffix='.pending', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Same-directory hard link atomically publishes the complete inode and
        # refuses existing destinations, including symlinks. No check/rename race.
        os.link(temporary, path)
    finally:
        os.unlink(temporary)
    if os.name == 'posix':
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def create_key(path):
    key = ec.generate_private_key(ec.SECP256R1())
    private_write(path, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    return key


def load_key(path):
    with regular_reader(path) as stream:
        data = stream.read(16_385)
    if len(data) > 16_384:
        raise Rejected('key_file_too_large')
    key = serialization.load_pem_private_key(data, password=None)
    public_bytes(key)  # Restrict curve and algorithm even for local key files.
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise Rejected('invalid_private_key')
    return key
