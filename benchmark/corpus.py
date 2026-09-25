"""Build a local Open Images starter corpus with attribution and disjoint authors.

Downloads only from the official metadata host and the CVDF public bucket.
No credentials, paid API, image uploads, or arbitrary URLs from metadata.
"""
import argparse
import concurrent.futures
import csv
import hashlib
import io
import json
import time
import urllib.request
from pathlib import Path
from PIL import Image

METADATA_URL = 'https://storage.googleapis.com/openimages/2018_04/validation/validation-images-with-rotation.csv'
SEED = 'proofcam-photo-corpus-v1'
ROOT = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fetch(url, limit):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError('download exceeds limit')
            return data
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def author_group(row):
    return row['AuthorProfileURL'].rstrip('/') or row['OriginalLandingURL'].rstrip('/')


def split_for(group):
    # Whole authors stay in one split; split is independent of download success.
    bucket = int(sha((SEED + group).encode())[:8], 16) % 10
    return 'tuning' if bucket < 2 else 'negative' if bucket == 2 else 'heldout'


def acquire(row):
    image_id = row['ImageID']
    if len(image_id) != 16 or any(c not in '0123456789abcdef' for c in image_id):
        raise ValueError('invalid source ID')
    path = ROOT / 'data/media' / (image_id + '.jpg')
    url = f'https://open-images-dataset.s3.amazonaws.com/validation/{image_id}.jpg'
    data = path.read_bytes() if path.exists() else fetch(url, 25 * 1024 * 1024)
    with Image.open(io.BytesIO(data)) as im:
        if im.format != 'JPEG' or im.width * im.height > 20_000_000:
            raise ValueError('unsupported source')
        im.load()
        width, height = im.size
        # Exact decoded-pixel duplicates are rejected during selection.
        pixel_sha = sha(f'{width},{height}:'.encode() + im.convert('RGB').tobytes())
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.part')
        temp.write_bytes(data)
        temp.replace(path)
    return {
        'id': 'oi-' + image_id, 'source_id': image_id,
        'source_group': sha(author_group(row).encode()), 'split': split_for(author_group(row)),
        'path': str(path.relative_to(ROOT)), 'sha256': sha(data), 'pixel_sha256': pixel_sha,
        'width': width, 'height': height, 'kind': 'natural_photo_candidate',
        'license': row['License'], 'license_status': 'dataset_declared_not_individually_reviewed',
        'author': row['Author'], 'title': row['Title'], 'source_page': row['OriginalLandingURL'],
        'download_url': url, 'dataset_rotation': row['Rotation'],
        'tags': [], 'review_status': 'unreviewed', 'device': 'dataset-not-device-capture',
        'watermark_status': 'not_embedded_by_proofcam_not_certified_unmarked'
    }


def restore(manifest):
    lock = json.loads(manifest.with_suffix('.lock.json').read_text())
    if sha(manifest.read_bytes()) != lock['manifest_sha256']:
        raise ValueError('manifest changed since lock')
    records = [json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
    def restore_one(record):
        image_id = record['source_id']
        if len(image_id) != 16 or any(c not in '0123456789abcdef' for c in image_id):
            raise ValueError('invalid source ID')
        path = ROOT / 'data/media' / (image_id + '.jpg')
        data = path.read_bytes() if path.exists() else fetch(
            f'https://open-images-dataset.s3.amazonaws.com/validation/{image_id}.jpg', 25 * 1024 * 1024)
        if sha(data) != record['sha256']:
            raise ValueError('source changed; refusing to replace frozen bytes: ' + image_id)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.part')
            temporary.write_bytes(data)
            temporary.replace(path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for _ in pool.map(restore_one, records):
            pass
    print(f'Restored/verified {len(records)} locked source files. Manifest unchanged.', flush=True)


def prepare(args):
    manifest = ROOT / 'manifests/openimages-starter.jsonl'
    if manifest.exists():
        restore(manifest)
        return
    metadata = ROOT / 'data/source-metadata/openimages-validation.csv'
    metadata.parent.mkdir(parents=True, exist_ok=True)
    if not metadata.exists():
        metadata.write_bytes(fetch(METADATA_URL, 40 * 1024 * 1024))
    with metadata.open(newline='', encoding='utf-8') as stream:
        rows = [r for r in csv.DictReader(stream)
                if r['License'].rstrip('/') == 'https://creativecommons.org/licenses/by/2.0'
                and author_group(r)]
    rows.sort(key=lambda r: sha((SEED + r['ImageID']).encode()))
    quotas = {'tuning': args.tuning, 'heldout': args.heldout, 'negative': args.negative}
    counts = dict.fromkeys(quotas, 0)
    selected, failures, seen_bytes, seen_pixels, seen_authors = [], [], set(), set(), set()
    candidates = []
    # One image per author reduces obvious near-duplicate/session contamination.
    for r in rows:
        group = author_group(r)
        if group not in seen_authors:
            candidates.append(r)
            seen_authors.add(group)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        cursor = 0
        while any(counts[s] < quotas[s] for s in quotas) and cursor < len(candidates):
            batch = []
            batch_counts = dict.fromkeys(quotas, 0)
            while cursor < len(candidates) and len(batch) < 24:
                r = candidates[cursor]
                cursor += 1
                s = split_for(author_group(r))
                if counts[s] + batch_counts[s] < quotas[s]:
                    batch.append(r)
                    batch_counts[s] += 1
            if not batch:
                continue
            futures = [pool.submit(acquire, r) for r in batch]
            # Consume in deterministic order, not completion order.
            for r, future in zip(batch, futures):
                try:
                    item = future.result()
                    if item['sha256'] in seen_bytes or item['pixel_sha256'] in seen_pixels:
                        raise ValueError('duplicate bytes or decoded pixels')
                    seen_bytes.add(item['sha256']); seen_pixels.add(item['pixel_sha256'])
                    selected.append(item); counts[item['split']] += 1
                except Exception as exc:
                    failures.append({'source_id': r['ImageID'], 'error': type(exc).__name__})
            print(json.dumps({'downloaded': counts, 'failures': len(failures)}), flush=True)
    if counts != quotas:
        raise ValueError(f'not enough eligible sources: {counts} vs {quotas}')
    manifest = ROOT / 'manifests/openimages-starter.jsonl'
    manifest.parent.mkdir(exist_ok=True)
    contents = ''.join(json.dumps(r, sort_keys=True, ensure_ascii=False) + '\n' for r in sorted(selected, key=lambda r:r['id']))
    if manifest.exists() and manifest.read_text() != contents:
        raise ValueError('refusing to change an existing manifest; create a separately versioned corpus')
    manifest.write_text(contents)
    lock = {'schema': 1, 'status': 'starter_snapshot_not_release_frozen', 'seed': SEED,
            'manifest_sha256': sha(contents.encode()), 'metadata_sha256': sha(metadata.read_bytes()),
            'metadata_url': METADATA_URL, 'counts': counts, 'download_failures': failures,
            'limitations': ['License and visual-content review pending', 'No real-device screenshots',
                           'Negative pool not certified free of all watermarks', 'Not the 300000-input release corpus']}
    (manifest.parent / 'openimages-starter.lock.json').write_text(json.dumps(lock, indent=2) + '\n')
    print('Starter manifest and content lock written. This is not release qualification.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tuning', type=int, default=100)
    parser.add_argument('--heldout', type=int, default=1000)
    parser.add_argument('--negative', type=int, default=100)
    args = parser.parse_args()
    if min(args.tuning, args.heldout, args.negative) < 1:
        parser.error('all splits require at least one source')
    prepare(args)
