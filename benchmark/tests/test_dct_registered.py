import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from benchmark.candidates import dct_registered as d
from benchmark import harness as h


class RegisteredDctTests(unittest.TestCase):
    def test_roundtrip_and_arbitrary_uniform_border(self):
        image = Image.fromarray(np.random.default_rng(14).integers(40, 210, (768, 1024, 3), dtype=np.uint8))
        identifier = 'fedcba9876543210' * 2
        for candidate in d.CONFIGS:
            encoded = h.decode(h.jpeg(d.embed(image, identifier, candidate)))
            canvas = Image.new('RGB', (1102, 934), (71, 18, 92))
            canvas.paste(encoded, (31, 97))
            with self.subTest(candidate=candidate):
                self.assertEqual(d.uniform_border_box(canvas), (31, 97, 1055, 865))
                ids, attempts = d.extract(canvas, candidate)
                self.assertEqual(ids, [identifier])
                self.assertLessEqual(len(attempts), d.MAX_ATTEMPTS)

    def test_conflicting_ids_survive_full_search(self):
        image = Image.new('RGB', (512, 512), 'gray')
        with patch.object(d, 'extract_view', side_effect=['01' * 16, '02' * 16]) as decoder:
            identifiers, attempts = d.extract(image)
        self.assertEqual(identifiers, ['01' * 16, '02' * 16])
        self.assertEqual(decoder.call_count, 2)
        self.assertEqual(len(attempts), 2)

    def test_flat_negative_and_border_rejection(self):
        image = Image.new('RGB', (512, 512), 'gray')
        self.assertIsNone(d.uniform_border_box(image))
        self.assertEqual(d.extract(image)[0], [])
        tiny = image.copy(); tiny.paste(Image.new('RGB', (10, 10), 'white'), (250, 250))
        self.assertIsNone(d.uniform_border_box(tiny))
        with self.assertRaises(KeyError): d.extract(image, 'unknown')
