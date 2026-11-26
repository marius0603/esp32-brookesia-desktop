"""Exercise separation and false-trigger rejection on synthetic readings."""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from calibrate_rssi import load_samples, suggest


class CalibrationTests(unittest.TestCase):
    def test_separated_groups(self):
        groups = {300: [-83] * 16, 200: [-76] * 16, 100: [-68] * 16,
                  50: [-61, -59, -60, -60] * 4, 30: [-49, -51, -50, -50] * 4}
        cutoff, gap = suggest(groups)
        self.assertEqual(cutoff, -55)
        self.assertEqual(gap, 8)

    def test_overlapping_nearby_groups(self):
        cutoff, gap = suggest({30: [-61] * 16, 50: [-59] * 16, 100: [-70] * 16})
        self.assertIsNone(cutoff)
        self.assertEqual(gap, -2)

    def test_consecutive_far_bursts_reject_threshold(self):
        far = [-70] * 18 + [-50] * 3 + [-70] * 19
        cutoff, gap = suggest({30: [-50] * 16, 50: far})
        self.assertGreaterEqual(gap, 6)
        self.assertIsNone(cutoff)

    def test_require_both_sides(self):
        with self.assertRaisesRegex(ValueError, '距离内外'):
            suggest({30: [-50] * 16})

    def test_parse_samples_and_reject_invalid_rows(self):
        data = 'distance_cm,rssi_dbm\n' + '30,-51\n' * 16
        self.assertEqual(load_samples(io.StringIO(data))[30], [-51] * 16)
        with self.assertRaisesRegex(ValueError, '超出范围'):
            load_samples(io.StringIO(data + '30,127\n'))


if __name__ == '__main__':
    unittest.main()
