"""Exercise separation and false-trigger rejection on synthetic readings."""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from calibrate_rssi import load_samples, suggest


class CalibrationTests(unittest.TestCase):
    def test_separated_groups(self):
        groups = {50: [-83] * 16, 30: [-76] * 16, 20: [-68] * 16,
                  15: [-61, -59, -60, -60] * 4, 10: [-49, -51, -50, -50] * 4, 5: [-45] * 16}
        cutoff, gap = suggest(groups)
        self.assertEqual(cutoff, -55)
        self.assertEqual(gap, 8)

    def test_overlapping_nearby_groups(self):
        cutoff, gap = suggest({10: [-61] * 16, 15: [-59] * 16, 50: [-70] * 16})
        self.assertIsNone(cutoff)
        self.assertEqual(gap, -2)

    def test_consecutive_far_bursts_reject_threshold(self):
        far = [-70] * 18 + [-50] * 3 + [-70] * 19
        cutoff, gap = suggest({10: [-50] * 16, 15: far})
        self.assertGreaterEqual(gap, 6)
        self.assertIsNone(cutoff)

    def test_require_both_sides(self):
        with self.assertRaisesRegex(ValueError, '距离内外'):
            suggest({10: [-50] * 16})

    def test_require_samples_at_exact_target_distance(self):
        with self.assertRaisesRegex(ValueError, '目标距离 10 厘米'):
            suggest({5: [-50] * 16, 15: [-70] * 16})

    def test_parse_samples_and_reject_invalid_rows(self):
        data = 'distance_cm,rssi_dbm\n' + '30,-51\n' * 16
        self.assertEqual(load_samples(io.StringIO(data))[30], [-51] * 16)
        with self.assertRaisesRegex(ValueError, '超出范围'):
            load_samples(io.StringIO(data + '30,127\n'))


if __name__ == '__main__':
    unittest.main()
