"""Blind block-DCT baselines with repeated 176-bit frames. Research only."""
import re
import zlib
import numpy as np
from PIL import Image
from scipy.fft import dctn, idctn

FRAME_BITS = 176
CONFIGS = {'pair24': {'method': 'pair', 'strength': 24.0},
           'qim48': {'method': 'qim', 'strength': 48.0}}


def frame(identifier):
    if not isinstance(identifier, str) or not re.fullmatch('[0-9a-f]{32}', identifier):
        raise ValueError('Expected a complete lowercase 128-bit hex ID')
    body = b'PC' + bytes.fromhex(identifier)
    return np.unpackbits(np.frombuffer(body + zlib.crc32(body).to_bytes(4, 'big'), dtype=np.uint8))


def parse(bits):
    if len(bits) != FRAME_BITS:
        return None
    raw = np.packbits(bits).tobytes()
    if raw[:2] != b'PC' or zlib.crc32(raw[:18]).to_bytes(4, 'big') != raw[18:]:
        return None
    return raw[2:18].hex()


def coefficients(image):
    if image.width * image.height > 20_000_000 or max(image.size) > 16384:
        raise ValueError('Input exceeds research dimension limits')
    rgb = np.asarray(image.convert('RGB'), dtype=np.float32)
    height, width = (image.height // 8) * 8, (image.width // 8) * 8
    if (height // 8) * (width // 8) < FRAME_BITS * 3:
        raise ValueError('At least three complete frames required')
    luma = rgb[:height, :width] @ np.array([.299, .587, .114], dtype=np.float32)
    blocks = luma.reshape(height // 8, 8, width // 8, 8).transpose(0, 2, 1, 3)
    return rgb, luma, dctn(blocks, axes=(-2, -1), norm='ortho', workers=1)


def embed(image, identifier, candidate='pair24'):
    config = CONFIGS[candidate]
    payload = frame(identifier)
    rgb, luma, coeff = coefficients(image)
    shape = coeff.shape
    coeff = coeff.reshape(-1, 8, 8)
    bits = np.resize(payload, len(coeff))
    strength = config['strength']
    if config['method'] == 'pair':
        first, second = coeff[:, 2, 3], coeff[:, 3, 2]
        sign = bits.astype(np.float32) * 2 - 1
        change = np.maximum(0, strength - sign * (first - second)) / 2
        first += sign * change
        second -= sign * change
    else:
        values = coeff[:, 2, 3] / strength
        coeff[:, 2, 3] = (2 * np.rint((values - bits) / 2) + bits) * strength
    restored = idctn(coeff.reshape(shape), axes=(-2, -1), norm='ortho', workers=1)
    restored = restored.transpose(0, 2, 1, 3).reshape(luma.shape)
    rgb[:luma.shape[0], :luma.shape[1]] += (restored - luma)[..., None]
    return Image.fromarray(np.clip(np.rint(rgb), 0, 255).astype(np.uint8))


def extract(image, candidate='pair24'):
    """Only pixels and pinned configuration; never receives expected/source IDs."""
    config = CONFIGS[candidate]
    _, _, coeff = coefficients(image)
    coeff = coeff.reshape(-1, 8, 8)
    if config['method'] == 'pair':
        votes = (coeff[:, 2, 3] > coeff[:, 3, 2]).astype(np.int32)
    else:
        votes = np.rint(coeff[:, 2, 3] / config['strength']).astype(np.int32) % 2
    indices = np.arange(len(votes)) % FRAME_BITS
    ones = np.bincount(indices, weights=votes, minlength=FRAME_BITS)
    total = np.bincount(indices, minlength=FRAME_BITS)
    if np.any(ones * 2 == total):
        return None  # No arbitrary tie-breaking into a supposedly valid identifier.
    return parse((ones * 2 > total).astype(np.uint8))
