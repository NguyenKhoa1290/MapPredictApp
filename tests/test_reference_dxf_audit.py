"""Survey-only spatial tests. No user DXF changes or inferred CRS."""
import unittest

from shapely.geometry import box

from tools.audit_reference_dxf import geometry_summary, label_summary


def label(x, y, text="1"):
    return {"text": text, "handle": "T1", "kind": "TEXT", "position": [x, y, 0]}


class ReferenceDxfAuditTests(unittest.TestCase):
    def test_inside_label_is_unique(self):
        result = label_summary([box(0, 0, 20, 20)], [label(5, 5)])
        self.assertEqual(result["strict_insert_statuses"],
                         {"unique_inside": 1, "boundary_or_overlap": 0, "outside": 0})

    def test_shared_edge_is_not_assigned(self):
        result = label_summary([box(0, 0, 20, 20), box(20, 0, 40, 20)], [label(20, 5)])
        self.assertEqual(result["strict_insert_statuses"]["boundary_or_overlap"], 1)
        self.assertEqual(result["cells_without_unique_insert_label"], 2)

    def test_duplicate_polygon_is_reported_not_removed(self):
        a = box(0, 0, 20, 20)
        b = box(0, 0, 20, 20)
        result = geometry_summary([a, b], ["P1", "P2"])
        self.assertEqual(result["polygons"], 2)
        self.assertEqual(result["unique_exact_geometries"], 1)
        self.assertEqual(result["duplicate_geometry_groups"], [["P1", "P2"]])
        self.assertEqual(result["duplicate_extra_polygons"], 1)
        self.assertEqual(label_summary([a, b], [label(5, 5)])
                         ["strict_insert_statuses"]["boundary_or_overlap"], 1)

    def test_tiny_outside_offset_does_not_snap(self):
        result = label_summary([box(0, 0, 20, 20)], [label(-1e-10, 5)])
        self.assertEqual(result["strict_insert_statuses"]["outside"], 1)
        self.assertAlmostEqual(result["outside_labels"][0]
                               ["distance_to_grid_raw_units_diagnostic_only"], 1e-10)

    def test_unlabelled_cells_remain_in_geometry_count(self):
        polygons = [box(0, 0, 20, 20), box(20, 0, 40, 20)]
        result = label_summary(polygons, [label(5, 5)])
        self.assertEqual(result["cells_without_unique_insert_label"], 1)
        self.assertEqual(geometry_summary(polygons, ["P1", "P2"])
                         ["overlap_pairs_above_raw_area_1e_minus_5"], [])


if __name__ == "__main__":
    unittest.main()
