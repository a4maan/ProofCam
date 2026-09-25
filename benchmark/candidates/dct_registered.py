"""Lower-distortion QIM with a bounded, pixel-only scale/border search."""
import numpy as np
from PIL import Image
from scipy.fft import idctn
from benchmark.candidates import dct_baseline as base

CONFIGS = {'qim12_registered': {'strength': 12.0},
           'qim20_registered': {'strength': 20.0}}
FRAME_BITS = base.FRAME_BITS
TARGET_EDGE = 1024
MAX_ATTEMPTS = 4


def embed(image, identifier, candidate='qim12_registered'):
    payload = base.frame(identifier)
    rgb, luma, coefficients = base.coefficients(image)
    shape = coefficients.shape
    flat = coefficients.reshape(-1, 8, 8)
    bits = np.resize(payload, len(flat))
    strength = CONFIGS[candidate]['strength']
    values = flat[:, 1, 2] / strength
    flat[:, 1, 2] = (2 * np.rint((values - bits) / 2) + bits) * strength
    restored = idctn(flat.reshape(shape), axes=(-2, -1), norm='ortho', workers=1)
    restored = restored.transpose(0, 2, 1, 3).reshape(luma.shape)
    rgb[:luma.shape[0], :luma.shape[1]] += (restored - luma)[..., None]
    return Image.fromarray(np.clip(np.rint(rgb), 0, 255).astype(np.uint8))


def uniform_border_box(image):
    """Trim only contiguous, exactly uniform outer bands sharing the corner color.

    Works for simple letterboxes; not an Android UI or arbitrary media detector.
    No known synthetic-canvas color, margin, source size, or expected ID is used.
    """
    pixels = np.asarray(image.convert('RGB'))
    matching = np.all(pixels == pixels[0, 0], axis=2)
    rows, columns = np.all(matching, axis=1), np.all(matching, axis=0)
    ys, xs = np.flatnonzero(~rows), np.flatnonzero(~columns)
    if not len(xs) or not len(ys):
        return None
    box = (int(xs[0]), int(ys[0]), int(xs[-1]) + 1, int(ys[-1]) + 1)
    if box == (0, 0, image.width, image.height):
        return None
    if (box[2] - box[0]) * (box[3] - box[1]) < image.width * image.height * .25:
        return None
    return box


def search_views(image):
    if image.width * image.height > 20_000_000 or max(image.size) > 16384:
        raise ValueError('Input exceeds research dimension limits')
    image = image.convert('RGB')
    regions = [('whole', image, (0, 0, image.width, image.height))]
    box = uniform_border_box(image)
    if box is not None:
        regions.append(('uniform_border_trim', image.crop(box), box))
    for region, view, rectangle in regions:
        yield region + ':native', view, rectangle
        if max(view.size) != TARGET_EDGE:
            ratio = TARGET_EDGE / max(view.size)
            size = tuple(max(1, round(value * ratio)) for value in view.size)
            yield region + ':edge1024', view.resize(size, Image.Resampling.LANCZOS), rectangle


def extract_view(image, candidate):
    _, _, coefficients = base.coefficients(image)
    flat = coefficients.reshape(-1, 8, 8)
    votes = np.rint(flat[:, 1, 2] / CONFIGS[candidate]['strength']).astype(np.int32) % 2
    indices = np.arange(len(votes)) % FRAME_BITS
    ones = np.bincount(indices, weights=votes, minlength=FRAME_BITS)
    total = np.bincount(indices, minlength=FRAME_BITS)
    if np.any(ones * 2 == total):
        return None
    return base.parse((ones * 2 > total).astype(np.uint8))


def extract(image, candidate='qim12_registered'):
    CONFIGS[candidate]  # Reject invalid configuration before search.
    recovered, attempts = set(), []
    for geometry, view, rectangle in search_views(image):
        try:
            identifier = extract_view(view, candidate)
            status = 'searched'
        except ValueError:
            identifier, status = None, 'insufficient_capacity'
        if identifier is not None:
            recovered.add(identifier)
        attempts.append({'geometry': geometry, 'size': list(view.size), 'rectangle': list(rectangle),
                         'status': status, 'decoded_id': identifier})
    assert len(attempts) <= MAX_ATTEMPTS
    # Search every declared geometry even after success; preserve conflicting IDs.
    return sorted(recovered), attempts
