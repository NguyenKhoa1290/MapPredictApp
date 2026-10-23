import io
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import ezdxf
from shapely.geometry import shape

import app as python_app
from gis import cad_geojson, gpkg_columns, predicted_geojson


def sample_drawing(path):
    document = ezdxf.new()
    document.layers.new("roads", dxfattribs={"color": 3})
    document.layers.new("plots", dxfattribs={"color": 1})
    space = document.modelspace()
    for index in range(125):
        space.add_line((515100 + index * 2, 2402100), (515100 + index * 2, 2402300), dxfattribs={"layer": "roads"})
    space.add_circle((515220, 2402220), 20, dxfattribs={"layer": "plots"})
    space.add_arc((515170, 2402220), 15, 0, 120, dxfattribs={"layer": "plots"})
    space.add_ellipse((515170, 2402170), (20, 0), 0.5, dxfattribs={"layer": "plots"})
    space.add_spline([(515100, 2402100), (515110, 2402120), (515120, 2402110), (515140, 2402150)], dxfattribs={"layer": "roads"})
    space.add_point((515150, 2402150), dxfattribs={"layer": "plots"})
    space.add_lwpolyline([(515200, 2402100, 1), (515230, 2402100, 0)], format="xyb", dxfattribs={"layer": "roads"})
    hatch = space.add_hatch(color=2, dxfattribs={"layer": "plots"})
    hatch.paths.add_polyline_path([(515260, 2402110), (515300, 2402110), (515300, 2402150), (515260, 2402150)], is_closed=True)
    hatch.paths.add_polyline_path([(515270, 2402120), (515290, 2402120), (515290, 2402140), (515270, 2402140)], is_closed=True)
    space.add_solid([(515300, 2402200), (515320, 2402200), (515300, 2402220)], dxfattribs={"layer": "plots"})
    space.add_3dface([(515300, 2402250), (515320, 2402250), (515300, 2402270)], dxfattribs={"layer": "plots"})
    block = document.blocks.new("survey-marker")
    block.add_line((0, 0), (5, 5), dxfattribs={"color": 0})
    space.add_blockref(block.name, (515330, 2402200), dxfattribs={"layer": "roads", "color": 5})
    space.add_text("Do not display CAD labels", dxfattribs={"layer": "plots"})
    space.add_xline((515100, 2402100), (1, 0))
    document.saveas(path)
    return document


class MapLayerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.result_patch = patch.object(python_app, "RESULT_CSV", self.root / "results.csv")
        self.data_patch = patch.object(python_app, "DATA_DIR", self.root)
        self.result_patch.start(); self.data_patch.start()
        self.client = python_app.app.test_client()

    def tearDown(self):
        self.result_patch.stop(); self.data_patch.stop()
        self.directory.cleanup()

    def test_cad_curves_points_hatches_and_source_metadata(self):
        path = self.root / "mixed.dxf"
        sample_drawing(path)
        before = path.read_bytes()
        collection = cad_geojson(path, "EPSG:9208")
        self.assertEqual(path.read_bytes(), before)
        features = collection["features"]
        kinds = {feature["properties"]["entity_type"] for feature in features}
        self.assertTrue({"LINE", "CIRCLE", "ARC", "ELLIPSE", "SPLINE", "POINT", "HATCH", "SOLID", "3DFACE"} <= kinds)
        self.assertNotIn("TEXT", kinds)
        circle = next(feature for feature in features if feature["properties"]["entity_type"] == "CIRCLE")
        self.assertGreater(len(circle["geometry"]["coordinates"]), 20)
        hatch = next(feature for feature in features if feature["properties"]["entity_type"] == "HATCH")
        self.assertEqual(len(hatch["geometry"]["coordinates"]), 2)
        self.assertTrue(shape(hatch["geometry"]).is_valid)
        curved_polyline = next(feature for feature in features if feature["properties"]["entity_type"] == "LWPOLYLINE")
        self.assertGreater(len(curved_polyline["geometry"]["coordinates"]), 2)
        road = next(feature for feature in features if feature["properties"]["layer"] == "roads" and not feature["properties"]["block"])
        self.assertEqual(road["properties"]["color"], "#00ff00")
        child = next(feature for feature in features if feature["properties"]["block"] == "survey-marker")
        self.assertEqual(child["properties"]["layer"], "roads")
        self.assertEqual(child["properties"]["color"], "#0000ff")
        self.assertTrue(any("XLINE" in reason for reason in collection["warnings"]))

    def test_multiple_prediction_files_and_dxf_have_stable_source_ids(self):
        path = self.root / "mixed.dxf"; sample_drawing(path)
        data = (python_app.ROOT / "layer_du_doan.gpkg").read_bytes()
        response = self.client.post("/api/map", data={
            "source_crs": "EPSG:9208", "cad": (io.BytesIO(path.read_bytes()), "mixed.dxf"),
            "cad_id": "cad-one", "layer_id": ["prediction-one", "prediction-two"],
            "layer": [(io.BytesIO(data), "first.gpkg"), (io.BytesIO(data), "second.gpkg")],
            "result": (io.BytesIO(b"fid,Y\n1,2\n"), "results.csv"), "gpkg_join": "fid", "csv_join": "fid",
        })
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual([layer["source_id"] for layer in response.json["layers"]], ["cad-one", "prediction-one", "prediction-two"])
        self.assertEqual([layer["name"] for layer in response.json["layers"]], ["mixed.dxf", "first.gpkg", "second.gpkg"])
        self.assertEqual(len(response.json["layers"][1]["data"]["features"]), len(response.json["layers"][2]["data"]["features"]))

    def test_prediction_keeps_attributes_and_every_geometry_table(self):
        path = self.root / "multiple-tables.gpkg"
        shutil.copyfile(python_app.ROOT / "layer_du_doan.gpkg", path)
        with closing(sqlite3.connect(path)) as connection:
            table, column, kind, srs = connection.execute("SELECT table_name,column_name,geometry_type_name,srs_id FROM gpkg_geometry_columns LIMIT 1").fetchone()
            quote = lambda text: '"' + text.replace('"', '""') + '"'
            connection.execute(f"CREATE TABLE extra AS SELECT * FROM {quote(table)} LIMIT 2")
            connection.execute("ALTER TABLE extra ADD COLUMN note TEXT")
            connection.execute("UPDATE extra SET note = 'extra details'")
            connection.execute("INSERT INTO gpkg_geometry_columns VALUES (?,?,?,?,0,0)", ("extra", column, kind, srs))
            connection.commit()
        collection = predicted_geojson(path, [{"fid": "1", "Y": "2"}], "fid", "fid", "EPSG:9208")
        extra = [feature for feature in collection["features"] if feature["properties"]["source_table"] == "extra"]
        self.assertEqual(len(extra), 2)
        self.assertEqual(extra[0]["properties"]["note"], "extra details")
        self.assertGreater(len(extra[0]["properties"]), 5)
        self.assertIn("fid", gpkg_columns(path))
        self.assertNotIn("note", gpkg_columns(path))


if __name__ == "__main__":
    unittest.main()
