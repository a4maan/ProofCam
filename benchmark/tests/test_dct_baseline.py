import unittest
import numpy as np
from PIL import Image
from benchmark.candidates import dct_baseline as d
from benchmark import harness as h


class DctBaselineTests(unittest.TestCase):
    def test_frame_checks_full_id_and_corruption(self):
        identifier = '0123456789abcdef' * 2
        bits = d.frame(identifier)
        self.assertEqual(len(bits), 176)
        self.assertEqual(d.parse(bits), identifier)
        for position in (0, 16, 80, 175):
            damaged = bits.copy(); damaged[position] ^= 1
            self.assertIsNone(d.parse(damaged))
        for invalid in ('x' * 32, 'abc', 'A' * 32, None):
            with self.assertRaises(ValueError): d.frame(invalid)

    def test_blind_jpeg_roundtrip_for_both_methods_and_ids(self):
        image = Image.fromarray(np.random.default_rng(123).integers(30, 226, (512, 512, 3), dtype=np.uint8))
        for candidate in d.CONFIGS:
            self.assertIsNone(d.extract(image, candidate))
            for identifier in ('01' * 16, 'fe' * 16):
                with self.subTest(candidate=candidate, identifier=identifier):
                    marked = h.decode(h.jpeg(d.embed(image, identifier, candidate)))
                    self.assertEqual(d.extract(marked, candidate), identifier)

    def test_capacity_and_flat_negative(self):
        for candidate in d.CONFIGS:
            with self.assertRaises(ValueError): d.extract(Image.new('RGB', (64, 64)), candidate)
            self.assertIsNone(d.extract(Image.new('RGB', (512, 512), 'gray'), candidate))
