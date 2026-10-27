import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ezdxf
from shapely.geometry import shape

import app as python_app
from prediction_grid import dxf_grid_metadata, predicted_dxf_grid, read_dxf_grid


def grid_document(ids=("10", "1", "2")):
    document = ezdxf.new()
    space = document.modelspace()
    for index, label in enumerate(ids):
        x, y = 515100 + index * 20, 2402100
        space.add_lwpolyline([(x, y), (x + 20, y), (x + 20, y + 20), (x, y + 20)], close=True)
        if label is not None:
            space.add_text(label, dxfattribs={"insert": (x + 5, y + 5), "height": 2})
        # Height is intentionally unrelated to identity: it must never be used.
        space.add_point((x + 5, y + 5, 999))
    return document


class PredictionGridTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.path = self.root / "grid.dxf"
        self.document = grid_document()
        self.document.saveas(self.path)
        self.result_path = self.root / "results.csv"
        self.result_patch = patch.object(python_app, "RESULT_CSV", self.result_path)
        self.data_patch = patch.object(python_app, "DATA_DIR", self.root)
        self.result_patch.start()
        self.data_patch.start()
        self.client = python_app.app.test_client()

    def tearDown(self):
        self.result_patch.stop()
        self.data_patch.stop()
        self.directory.cleanup()

    def test_closed_cells_and_derived_ids_not_native_tenlodat(self):
        before = self.path.read_bytes()
        collection = read_dxf_grid(self.path)
        self.assertEqual([f["properties"]["grid_id"] for f in collection["features"]], ["10", "1", "2"])
        self.assertEqual(collection["metadata"]["cell_count"], 3)
        self.assertEqual(collection["metadata"]["identified_count"], 3)
        self.assertNotIn("tenlodat", collection["metadata"]["columns"])
        for cell in collection["features"]:
            self.assertEqual(cell["geometry"]["type"], "Polygon")
            self.assertAlmostEqual(shape(cell["geometry"]).area, 400)
            self.assertEqual(cell["properties"]["id_source"], "TEXT/MTEXT")
            self.assertNotIn("tenlodat", cell["properties"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_join_uses_contained_label_not_order_and_keeps_unmatched(self):
        collection = predicted_dxf_grid(self.path, [{"tenlodat": " 1 ", "Y": "2"},
                                                  {"tenlodat": "10", "Y": "0"}],
                                        "grid_id", "tenlodat", "EPSG:9208")
        by_id = {f["properties"]["grid_id"]: f for f in collection["features"]}
        self.assertEqual(by_id["1"]["properties"]["Y"], 2)
        self.assertEqual(by_id["10"]["properties"]["Y"], 0)
        self.assertEqual(by_id["1"]["properties"]["fillColor"], "#008000")
        self.assertEqual(by_id["10"]["properties"]["fillColor"], "#ff0000")
        self.assertIsNone(by_id["2"]["properties"]["Y"])
        self.assertEqual(by_id["2"]["properties"]["fillOpacity"], 0)
        self.assertEqual(collection["join_summary"]["matched"], 2)
        self.assertEqual(collection["join_summary"]["unmatched"], 1)

    def test_preview_without_results_and_projection_offsets(self):
        preview = predicted_dxf_grid(self.path, [], "grid_id", "", "EPSG:9208")
        shifted = predicted_dxf_grid(self.path, [], "grid_id", "", "EPSG:9208", 100, 200)
        self.assertFalse(preview["join_summary"]["results_applied"])
        self.assertEqual(len(preview["features"]), 3)
        self.assertTrue(all(f["properties"]["Y"] is None for f in preview["features"]))
        west, south, east, north = shape(preview["features"][0]["geometry"]).bounds
        self.assertTrue(104 < west < east < 106)
        self.assertTrue(21 < south < north < 23)
        self.assertGreater(shape(shifted["features"][0]["geometry"]).bounds[0], west)
        self.assertGreater(shape(shifted["features"][0]["geometry"]).bounds[1], south)

    def test_missing_duplicate_and_ambiguous_labels_do_not_guess(self):
        doc = grid_document((None, "same", "same", "a"))
        doc.modelspace().add_text("b", dxfattribs={"insert": (515165, 2402106)})
        doc.saveas(self.path)
        collection = predicted_dxf_grid(self.path, [{"id": "same", "Y": "2"}, {"id": "a", "Y": "1"}],
                                        "grid_id", "id", "EPSG:9208")
        self.assertEqual([f["properties"]["id_status"] for f in collection["features"]],
                         ["missing", "duplicate", "duplicate", "ambiguous"])
        self.assertEqual(collection["join_summary"]["matched"], 0)
        self.assertEqual(len(collection["features"]), 4)

    def test_label_on_shared_boundary_is_not_assigned(self):
        doc = grid_document((None, None))
        doc.modelspace().add_text("shared", dxfattribs={"insert": (515120, 2402105)})
        doc.saveas(self.path)
        collection = read_dxf_grid(self.path)
        self.assertEqual([f["properties"]["id_status"] for f in collection["features"]], ["ambiguous", "ambiguous"])

    def test_mtext_and_legacy_polyline(self):
        doc = ezdxf.new()
        space = doc.modelspace()
        space.add_polyline2d([(515100, 2402100), (515120, 2402100), (515120, 2402120), (515100, 2402120)], close=True)
        space.add_mtext("cell-a", dxfattribs={"insert": (515105, 2402105)})
        doc.saveas(self.path)
        self.assertEqual(read_dxf_grid(self.path)["features"][0]["properties"]["grid_id"], "cell-a")

    def test_open_invalid_polylines_and_no_cells(self):
        space = self.document.modelspace()
        space.add_lwpolyline([(0, 0), (1, 1)], close=False)
        space.add_lwpolyline([(0, 0), (2, 2), (0, 2), (2, 0)], close=True)
        self.document.saveas(self.path)
        collection = read_dxf_grid(self.path)
        self.assertEqual(len(collection["features"]), 3)
        self.assertEqual(len(collection["warnings"]), 2)
        doc = ezdxf.new()
        doc.modelspace().add_line((0, 0), (1, 1))
        doc.saveas(self.path)
        with self.assertRaisesRegex(ValueError, "DXF"):
            read_dxf_grid(self.path)

    def test_invalid_join_and_conflicting_csv_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            predicted_dxf_grid(self.path, [{"id": "1", "Y": "2"}], "tenlodat", "id", "EPSG:9208")
        conflicts = predicted_dxf_grid(self.path, [{"id": "1", "Y": "2"}, {"id": "1", "Y": "0"}],
                                       "grid_id", "id", "EPSG:9208")
        self.assertEqual(conflicts["join_summary"]["ambiguous"], 1)
        self.assertTrue(all(item["properties"]["Y"] is None for item in conflicts["features"]))
        invalid = predicted_dxf_grid(self.path, [{"id": "1", "Y": "unknown"}], "grid_id", "id", "EPSG:9208")
        self.assertEqual(invalid["join_summary"]["matched"], 0)
        self.assertTrue(invalid["warnings"])

    def test_metadata_api_and_dxf_preview_api(self):
        data = self.path.read_bytes()
        response = self.client.post("/api/prediction-columns", data={"layer": (io.BytesIO(data), "grid.DXF")})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["format"], "dxf")
        self.assertEqual(response.json["suggested_join"], "grid_id")
        self.assertEqual(response.json["diagnostics"]["cell_count"], 3)
        self.assertIsNone(response.json["crs"])
        response = self.client.post("/api/map", data={"source_crs": "EPSG:9208", "layer_id": "grid-one",
            "layer": (io.BytesIO(data), "grid.dxf"), "layer_join": "grid_id"})
        self.assertEqual(response.status_code, 200, response.json)
        layer = response.json["layers"][0]
        self.assertEqual(layer["kind"], "prediction")
        self.assertEqual(layer["source_id"], "grid-one")
        self.assertEqual(len(layer["data"]["features"]), 3)
        self.assertFalse(self.result_path.exists())

    def test_mixed_dxf_gpkg_joins_and_legacy_columns_api(self):
        gpkg = (python_app.ROOT / "layer_du_doan.gpkg").read_bytes()
        columns = self.client.post("/api/prediction-columns", data={"layer": (io.BytesIO(gpkg), "a.gpkg")})
        self.assertEqual(columns.status_code, 200, columns.json)
        self.assertIn("fid", columns.json["columns"])
        response = self.client.post("/api/map", data={"source_crs": "EPSG:9208",
            "layer": [(io.BytesIO(self.path.read_bytes()), "grid.dxf"), (io.BytesIO(gpkg), "a.gpkg")],
            "layer_join": ["grid_id", "fid"], "csv_join": "id",
            "result": (io.BytesIO(b"id,Y\n1,2\n10,0\n"), "result.csv")})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual([layer["format"] for layer in response.json["layers"]], ["dxf", "gpkg"])
        self.assertEqual(response.json["layers"][0]["data"]["join_summary"]["matched"], 2)
        self.assertFalse(self.result_path.exists())

    def test_bad_grid_upload_does_not_replace_saved_results(self):
        self.result_path.write_bytes(b"id,Y\nold,1\n")
        response = self.client.post("/api/map", data={"source_crs": "EPSG:9208",
            "layer": (io.BytesIO(self.path.read_bytes()), "grid.dxf"), "layer_join": "nonexistent",
            "csv_join": "id", "result": (io.BytesIO(b"id,Y\n1,2\n"), "result.csv")})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.result_path.read_bytes(), b"id,Y\nold,1\n")


if __name__ == "__main__":
    unittest.main()
