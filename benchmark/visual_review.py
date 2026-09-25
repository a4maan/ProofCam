"""Validate a tuning-only visual-screening sidecar without granting approval."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

COHORTS = {'primary_photo_candidate', 'processed_photo_stress', 'artwork_stress',
           'composite_stress', 'document_stress', 'rendered_stress'}


def summarize(manifest, review_path):
    raw = Path(manifest).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    lock = json.loads(Path(manifest).with_suffix('.lock.json').read_text())
    review_bytes = Path(review_path).read_bytes()
    review = json.loads(review_bytes)
    if digest != lock['manifest_sha256'] or digest != review['source_manifest_sha256']:
        raise ValueError('Source manifest hash mismatch')
    if (review.get('schema_version') != 1 or review.get('release_approved') is not False
            or review.get('rights_review') != 'not_performed'):
        raise ValueError('Visual screening cannot grant rights or release approval')
    for field in ('reviewer', 'review_method', 'review_date', 'scope'):
        if not isinstance(review.get(field), str) or not review[field].strip():
            raise ValueError(f'Missing review provenance: {field}')
    sources = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len({r['id'] for r in sources}) != len(sources):
        raise ValueError('Duplicate source ID')
    tuning = {r['id']: r for r in sources if r['split'] == 'tuning'}
    seen = set()
    cohorts, tags = Counter(), Counter()
    for decision in review['decisions']:
        identifier = decision['id']
        if identifier in seen:
            raise ValueError('Duplicate review decision')
        seen.add(identifier)
        if identifier not in tuning or decision['split'] != 'tuning':
            raise ValueError('Review must remain tuning-only')
        if decision['source_sha256'] != tuning[identifier]['sha256']:
            raise ValueError('Reviewed source hash mismatch')
        cohort = decision['recommended_cohort']
        if cohort not in COHORTS:
            raise ValueError('Unknown cohort')
        if decision['inspection'] not in {'contact_sheet', 'source_resolution_and_contact_sheet'}:
            raise ValueError('Unknown inspection scope')
        observed = decision['observed_tags']
        if (not isinstance(observed, list) or any(not isinstance(t, str) or not t for t in observed)
                or len(set(observed)) != len(observed)):
            raise ValueError('Invalid observed tags')
        cohorts[cohort] += 1
        tags.update(observed)
    if seen != set(tuning):
        raise ValueError('Incomplete tuning review')
    return {'source_manifest_sha256': digest,
            'review_sha256': hashlib.sha256(review_bytes).hexdigest(),
            'reviewed_tuning_sources': len(seen), 'recommended_cohorts': dict(cohorts),
            'observed_tag_counts_non_exhaustive': dict(tags),
            'rights_approved_sources': 0, 'release_ready': False,
            'limitation': 'AI visual screening only; recommendations do not modify source manifests or approve rights, authenticity, or release eligibility.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('review', type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.manifest, args.review), indent=2))


if __name__ == '__main__':
    main()
