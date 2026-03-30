#!/usr/bin/env python3
"""Tests sans QGIS pour core.photo_patterns."""

import os
import sys
import unittest

# Racine du plugin sur sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.photo_patterns import (
    extract_coords_from_standard_filename,
    fid_from_photo_filename,
    group_contains_duplicate_same_fid,
)


class TestPhotoPatterns(unittest.TestCase):
    def test_fid_from_photo_filename(self):
        n = "DT_2025-01-15_42_maurin_eau_tas_fumier_544424.297_6005030.410.jpg"
        self.assertEqual(fid_from_photo_filename(n), 42)
        self.assertIsNone(fid_from_photo_filename(None))
        self.assertIsNone(fid_from_photo_filename("IMG_0001.jpg"))

    def test_extract_coords(self):
        n = "DT_2025-01-15_42_maurin_eau_tas_fumier_544424.297_6005030.410.jpg"
        x, y = extract_coords_from_standard_filename(n)
        self.assertAlmostEqual(x, 544424.297)
        self.assertAlmostEqual(y, 6005030.410)

    def test_group_same_fid(self):
        a = "DT_2025-01-15_5_a_t_1_2.jpg"
        b = "DT_2025-02-15_5_b_t_3_4.jpg"
        self.assertTrue(group_contains_duplicate_same_fid([a, b]))
        self.assertFalse(group_contains_duplicate_same_fid([a, "DT_2025-01-15_6_x_t_1_2.jpg"]))


if __name__ == "__main__":
    unittest.main()
