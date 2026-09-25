import copy
import json
from pathlib import Path
import tempfile
import unittest
from benchmark.visual_review import summarize

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'manifests/openimages-starter.jsonl'
REVIEW = ROOT / 'reviews/tuning-visual-v1.json'


class VisualReviewTests(unittest.TestCase):
    def test_recorded_review_is_complete_but_not_approval(self):
        report = summarize(MANIFEST, REVIEW)
        self.assertEqual(report['reviewed_tuning_sources'], 100)
        self.assertEqual(report['recommended_cohorts']['primary_photo_candidate'], 92)
        self.assertEqual(report['rights_approved_sources'], 0)
        self.assertFalse(report['release_ready'])

    def test_rejects_tampering_incomplete_cross_split_and_approval(self):
        original = json.loads(REVIEW.read_text())
        mutations = [lambda r: r.update(source_manifest_sha256='bad'),
                     lambda r: r.update(release_approved=True),
                     lambda r: r.update(rights_review='approved'),
                     lambda r: r['decisions'].pop(),
                     lambda r: r['decisions'].append(r['decisions'][0]),
                     lambda r: r['decisions'][0].update(split='heldout'),
                     lambda r: r['decisions'][0].update(source_sha256='bad'),
                     lambda r: r['decisions'][0].update(recommended_cohort='approved')]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'review.json'
            for index, mutate in enumerate(mutations):
                with self.subTest(mutation=index):
                    review = copy.deepcopy(original)
                    mutate(review)
                    path.write_text(json.dumps(review))
                    with self.assertRaises(ValueError):
                        summarize(MANIFEST, path)
