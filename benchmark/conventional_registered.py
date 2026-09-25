"""Compare registered QIM candidates on the exact v1 tuning sources and test IDs."""
import argparse
import json
import platform
import time
from pathlib import Path
import numpy as np
from benchmark import harness as h
from benchmark.visual_review import summarize
from benchmark.candidates import dct_registered as d
from benchmark.candidates import dct_baseline as base


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def run(out, limit):
    if limit != 24:
        raise ValueError('This comparison pins the same 24 v1 tuning sources')
    out.mkdir(parents=True, exist_ok=False)
    manifest = h.ROOT / 'manifests/openimages-starter.jsonl'
    review_path = h.ROOT / 'reviews/tuning-visual-v1.json'
    review_report = summarize(manifest, review_path)
    h.audit(manifest)
    recommendations = json.loads(review_path.read_text())['decisions']
    eligible = {r['id'] for r in recommendations if r['recommended_cohort'] == 'primary_photo_candidate'}
    rows = h.jsonl(manifest)
    positives = sorted((r for r in rows if r['split'] == 'tuning' and r['id'] in eligible), key=lambda r: r['id'])[:limit]
    negatives = sorted((r for r in rows if r['split'] == 'negative'), key=lambda r: r['id'])
    previous_path = h.ROOT / 'reports/conventional-v1/plan.json'
    previous = json.loads(previous_path.read_text())
    if [r['id'] for r in positives] != previous['positive_sources'] or [r['id'] for r in negatives] != previous['negative_sources']:
        raise ValueError('Comparison sources differ from v1')
    identifiers = previous['test_ids']
    for identifier in identifiers.values():
        base.frame(identifier)
    device = f'desktop-research-{platform.system()}-{platform.machine()}'
    plan = {'status': 'tuning_experiment_not_release_evaluation', 'environment': h.environment(),
            'review': review_report, 'candidate_code_sha256': h.digest(Path(d.__file__).read_bytes()),
            'runner_sha256': h.digest(Path(__file__).read_bytes()), 'configs': d.CONFIGS,
            'baseline_helper_sha256': h.digest(Path(base.__file__).read_bytes()),
            'comparison_plan_sha256': h.digest(previous_path.read_bytes()),
            'search_budget': {'max_attempts': d.MAX_ATTEMPTS, 'target_edge': d.TARGET_EDGE, 'early_exit': False},
            'selection': 'First N sorted primary-photo tuning candidates; all 100 starter negative candidates',
            'positive_sources': [r['id'] for r in positives], 'negative_sources': [r['id'] for r in negatives],
            'test_ids': identifiers, 'transforms': h.transforms(), 'device': device,
            'actual_screenshots': 0, 'android_measurements': 0,
            'limitations': ['Tuning results; not held-out validation', 'Unapproved rights and negative eligibility',
                           'Only native/1024-edge scale and exact uniform-border search; no crop or rotation registration',
                           'CRC is error detection, not authentication; copied/forged payloads remain possible',
                           'Desktop wall time includes Python/Pillow; not Android cost', 'Peak memory not measured']}
    h.dump(out / 'plan.json', plan)
    for candidate in d.CONFIGS:
        folder = out / candidate; folder.mkdir()
        cases, predictions, qualities, exports = [], [], [], []
        for index, source in enumerate(positives + negatives):
            positive = source['split'] == 'tuning'
            original = h.load_normalized(h.safe_media_path(source['path']))
            baseline = h.jpeg(original)
            if positive:
                start = time.perf_counter()
                exported = h.jpeg(d.embed(original, identifiers[source['id']], candidate))
                embed_ms = (time.perf_counter() - start) * 1000
                target = folder / (source['id'] + '.jpg'); target.write_bytes(exported)
                exports.append({'source_id': source['id'], 'expected_id': identifiers[source['id']],
                                'path': target.name, 'sha256': h.digest(exported)})
                qualities.append({'source_id': source['id'], 'embed_and_encode_ms': embed_ms,
                                  'repetitions_min': (original.width // 8) * (original.height // 8) // d.FRAME_BITS,
                                  **h.quality(h.decode(baseline), h.decode(exported))})
            else:
                exported = baseline
            for transform in h.transforms() if positive else ['original']:
                data, extension = h.transform(exported, transform)
                image = h.decode(data)
                case_id = source['id'] + '__' + transform
                # Inputs may be regenerated from retained exports; hashes pin the exact experiment.
                media_edge = min(int(transform.rsplit('_', 1)[1]), max(original.size)) if transform.startswith('synthetic_screenshot_') else max(image.size)
                bucket = 'synthetic-composite' if transform == 'synthetic_combined' else '1024+' if media_edge >= 1024 else '512-1023' if media_edge >= 512 else 'below-512'
                cases.append({'case_id': case_id, 'source_id': source['id'], 'source_group': source['source_group'],
                              'split': source['split'], 'transform': transform, 'device': device, 'size_bucket': bucket,
                              'kind': 'watermarked_candidate' if positive else 'negative_candidate',
                              'expected_id': identifiers[source['id']] if positive else None,
                              'sha256': h.digest(data), 'width': image.width, 'height': image.height,
                              'synthetic_screen': transform.startswith('synthetic_')})
                start = time.perf_counter()
                try:
                    recovered, attempts = d.extract(image, candidate)
                    status, complete, error = 'ok', True, None
                except ValueError as exc:
                    recovered, attempts, status, complete, error = [], [], 'unsupported', False, str(exc)
                elapsed = (time.perf_counter() - start) * 1000
                predictions.append({'case_id': case_id, 'status': status, 'search_complete': complete,
                                    'detected': bool(recovered), 'decoded_ids': recovered, 'attempts': attempts,
                                    'elapsed_ms': elapsed, 'error': error})
            if positive and (index + 1) % 8 == 0:
                print(f'{candidate}: {index + 1}/{len(positives)} tuning sources', flush=True)
        write_rows(folder / 'exports.jsonl', exports)
        write_rows(folder / 'cases.jsonl', cases)
        write_rows(folder / 'predictions.jsonl', predictions)
        write_rows(folder / 'quality.jsonl', qualities)
        report = h.score(cases, predictions)
        report.update(candidate=candidate, configuration=d.CONFIGS[candidate],
                      candidate_code_sha256=plan['candidate_code_sha256'], runner_sha256=plan['runner_sha256'],
                      baseline_helper_sha256=plan['baseline_helper_sha256'], search_budget=plan['search_budget'],
                      source_manifest_sha256=review_report['source_manifest_sha256'],
                      review_sha256=review_report['review_sha256'], environment=plan['environment'],
                      cases_sha256=h.digest((folder / 'cases.jsonl').read_bytes()),
                      predictions_sha256=h.digest((folder / 'predictions.jsonl').read_bytes()),
                      quality_sha256=h.digest((folder / 'quality.jsonl').read_bytes()),
                      actual_screenshots=0, android_measurements=0,
                      quality={'n': len(qualities),
                               'ssim_min': min(r['ssim_rgb_gaussian11'] for r in qualities),
                               'ssim_median': float(np.median([r['ssim_rgb_gaussian11'] for r in qualities])),
                               'psnr_min_db': min(r['psnr_db'] for r in qualities),
                               'embed_and_encode_p95_ms': float(np.percentile([r['embed_and_encode_ms'] for r in qualities], 95))})
        report['limitations'].extend(plan['limitations'])
        h.dump(folder / 'score.json', report)
        print(f'{candidate}: completed {len(cases)} cases', flush=True)
    h.dump(out / 'completed.json', {'status': 'complete_tuning_run', 'release_ready': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--limit', type=int, default=24)
    args = parser.parse_args()
    run(args.out, args.limit)
