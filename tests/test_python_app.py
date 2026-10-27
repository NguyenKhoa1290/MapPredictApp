import io
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import ezdxf
from pyproj import Transformer
from shapely.geometry import shape

import app as python_app
from gis import base_geojson, gpkg_diagnostics


class PythonAppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.result_path = Path(self.directory.name) / "KetQua.csv"
        self.result_patch = patch.object(python_app, "RESULT_CSV", self.result_path)
        self.data_patch = patch.object(python_app, "DATA_DIR", Path(self.directory.name))
        self.result_patch.start()
        self.data_patch.start()
        self.client = python_app.app.test_client()

    def tearDown(self):
        self.data_patch.stop()
        self.result_patch.stop()
        self.directory.cleanup()

    def test_default_model_predicts_without_shared_result_export(self):
        csv_data = b"id,x1,x2,x3,x4,x5,x6,x7,x8,x9\nlot-1,0,0,0,0,0,0,0,0,0\n"
        response = self.client.post("/api/predict", data={"csv": (io.BytesIO(csv_data), "input.csv")})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["rows"][0]["id"], "lot-1")
        self.assertIsInstance(response.json["rows"][0]["Y"], int)
        exported = self.client.get("/api/export")
        self.assertEqual(exported.status_code, 410)
        exported.close()
        self.assertEqual(self.client.get("/api/results").json["rows"], [])
        self.assertFalse(self.result_path.exists())

        uploaded = self.client.post("/api/predict", data={
            "csv": (io.BytesIO(csv_data), "input.csv"),
            "model": (io.BytesIO(b"blocked model upload"), "model.pkl"),
            "scaler": (io.BytesIO(b"blocked scaler upload"), "scaler.pkl"),
        })
        self.assertEqual(uploaded.status_code, 400, uploaded.json)
        self.assertEqual(self.client.get("/api/results").json["rows"], [])

    def test_old_shared_results_are_not_used_exported_or_overwritten(self):
        sentinel = b'id,Y\n1,2\n'
        self.result_path.write_bytes(sentinel)
        self.assertEqual(self.client.get('/api/results').json['rows'], [])
        self.assertEqual(self.client.get('/api/export').status_code, 410)
        predicted = self.client.post('/api/predict', data={'csv': (io.BytesIO(b'id,x1\nnew,0\n'), 'input.csv')})
        self.assertEqual(predicted.status_code, 200)
        document = ezdxf.new(); msp = document.modelspace()
        msp.add_lwpolyline([(500000, 2400000), (500020, 2400000), (500020, 2400020), (500000, 2400020)], close=True)
        msp.add_text('1', dxfattribs={'insert': (500010, 2400010)})
        stream = io.StringIO(); document.write(stream); grid = stream.getvalue().encode()
        for result in (None, sentinel):
            data = {'source_crs': 'EPSG:9208', 'layer': (io.BytesIO(grid), 'grid.dxf'), 'layer_join': 'grid_id', 'csv_join': 'id'}
            if result is not None: data['result'] = (io.BytesIO(result), 'result.csv')
            response = self.client.post('/api/map', data=data)
            self.assertEqual(response.status_code, 200, response.json)
            feature = response.json['layers'][0]['data']['features'][0]['properties']
            self.assertEqual(feature['Y'], None if result is None else 2)
            self.assertEqual(self.result_path.read_bytes(), sentinel)

    def test_home_serves_assets(self):
        self.assertEqual(self.client.get('/').location, '/portal/')
        self.assertEqual(self.client.get('/legacy/').location, '/portal/assessment')
        page = self.client.get("/legacy/?embedded=1")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"/static/leaflet/leaflet.js", page.data)
        self.assertIn(b"/static/app.css", page.data)
        self.assertIn(b"/static/favicon.png", page.data)
        self.assertIn(b"pdf_export.js", page.data)
        self.assertIn(b'id="map-export-pdf"', page.data)
        self.assertNotIn(b'id="workspace-save-now"', page.data)
        self.assertLess(page.data.index(b'id="map-button"'), page.data.index(b'id="map-export-pdf"'))
        page.close()
        asset = self.client.get("/static/app.js")
        self.assertEqual(asset.status_code, 200)
        self.assertIn(b"server.arcgisonline.com", asset.data)
        asset.close()
        leaflet_asset = self.client.get("/static/leaflet/leaflet.js")
        self.assertEqual(leaflet_asset.status_code, 200)
        leaflet_asset.close()

    def test_csv_preview_is_limited_and_does_not_save_results(self):
        csv_data = ("id,x1\n" + "".join(f"lot-{index},0\n" for index in range(250))).encode()
        with io.BytesIO(csv_data) as source:
            response = self.client.post("/api/preview-csv", data={"csv": (source, "input.csv")})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["count"], 250)
        self.assertEqual(len(response.json["rows"]), 200)
        self.assertFalse(self.result_path.exists())
        self.assertEqual(self.client.post("/api/preview-csv").status_code, 400)

    def test_geopackage_columns_and_prediction_layer(self):
        data = (python_app.ROOT / "layer_du_doan.gpkg").read_bytes()
        columns_stream = io.BytesIO(data)
        response = self.client.post("/api/gpkg-columns", data={"gpkg": (columns_stream, "layer.gpkg")})
        columns_stream.close()
        self.assertEqual(response.status_code, 200, response.json)
        self.assertIn("fid", response.json["columns"])
        self.assertEqual(response.json["crs"], "EPSG:5897")
        diagnosis = response.json["diagnostics"]
        self.assertEqual(diagnosis["declared_crs"], "EPSG:5897")
        self.assertEqual(diagnosis["geometry_srs_id"], 5897)
        self.assertGreater(sum(candidate["in_area"] for candidate in diagnosis["candidates"]), 1)
        response.close()

        layer_stream = io.BytesIO(data)
        result_stream = io.BytesIO(b"fid,Y\n1,2\n")
        response = self.client.post("/api/map", data={
            "source_crs": "EPSG:5897",
            "layer": (layer_stream, "layer.gpkg"),
            "result": (result_stream, "result.csv"),
            "gpkg_join": "fid",
            "csv_join": "fid",
        })
        layer_stream.close()
        result_stream.close()
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["output_crs"], "EPSG:4326")
        self.assertEqual(response.json["counts"]["2"], 1)
        self.assertTrue(response.json["layers"][0]["data"]["features"])
        matched = [feature for feature in response.json["layers"][0]["data"]["features"]
                   if feature["properties"]["fid"] == 1]
        self.assertEqual(matched[0]["properties"]["fillColor"], "#008000")
        west, south, east, north = shape(matched[0]["geometry"]).bounds
        self.assertTrue(102 < west < east < 110)
        self.assertTrue(8 < south < north < 24)
        response.close()

        corrected = self.client.post("/api/map", data={
            "layer": (io.BytesIO(data), "layer.gpkg"),
            "result": (io.BytesIO(b"fid,Y\n1,2\n"), "result.csv"),
            "gpkg_join": "fid", "csv_join": "fid",
            "source_crs": "EPSG:9213",
        })
        self.assertEqual(corrected.status_code, 200, corrected.json)
        self.assertEqual(corrected.json["layers"][0]["crs"], "EPSG:9213")
        self.assertEqual(corrected.json["layers"][0]["declared_crs"], "EPSG:5897")
        corrected_west = shape(corrected.json["layers"][0]["data"]["features"][0]["geometry"]).bounds[0]
        self.assertTrue(105 < corrected_west < 106)
        corrected.close()

    def test_uploaded_dxf_uses_requested_offset_and_shared_crs(self):
        path = Path(self.directory.name) / "local.dxf"
        document = ezdxf.new()
        document.modelspace().add_line((0, 0), (20, 20))
        document.saveas(path)
        data = path.read_bytes()
        x, y = Transformer.from_crs("EPSG:4326", "EPSG:5897", always_xy=True).transform(105, 21)
        with io.BytesIO(data) as source:
            response = self.client.post("/api/map", data={
                "cad": (source, "local.dxf"), "source_crs": "EPSG:5897",
                "cad_offset_x": str(x), "cad_offset_y": str(y),
            })
        self.assertEqual(response.status_code, 200, response.json)
        layer = response.json["layers"][0]
        self.assertEqual(layer["crs"], "EPSG:5897")
        shifted = layer["data"]["features"][0]["geometry"]["coordinates"][0]
        self.assertAlmostEqual(shifted[0], 105, places=4)
        self.assertAlmostEqual(shifted[1], 21, places=4)
        self.assertEqual(path.read_bytes(), data)
        for invalid in ({"cad_offset_x": "nan"}, {"source_crs": "EPSG:0"}):
            with io.BytesIO(data) as source:
                rejected = self.client.post("/api/map", data={
                    "cad": (source, "local.dxf"), "source_crs": "EPSG:5897", **invalid,
                })
            self.assertEqual(rejected.status_code, 400, rejected.json)

    def test_shared_crs_applies_to_dxf_and_prediction(self):
        data = (python_app.ROOT / "layer_du_doan.gpkg").read_bytes()
        path = Path(self.directory.name) / "base.dxf"
        document = ezdxf.new()
        source_xy = Transformer.from_crs("EPSG:4326", "EPSG:5897", always_xy=True).transform(105, 21)
        document.modelspace().add_line(source_xy, (source_xy[0] + 20, source_xy[1] + 20))
        document.saveas(path)
        response = self.client.post("/api/map", data={
            "cad": (io.BytesIO(path.read_bytes()), "base.dxf"),
            "layer": (io.BytesIO(data), "prediction.gpkg"),
            "result": (io.BytesIO(b"fid,Y\n1,2\n"), "result.csv"),
            "gpkg_join": "fid", "csv_join": "fid", "source_crs": "EPSG:9213",
        })
        self.assertEqual(response.status_code, 200, response.json)
        first, second = response.json["layers"]
        self.assertEqual(first["crs"], "EPSG:9213")
        self.assertEqual(second["crs"], "EPSG:9213")
        self.assertEqual(second["declared_crs"], "EPSG:5897")
        expected = Transformer.from_crs("EPSG:9213", "EPSG:4326", always_xy=True).transform(*source_xy)
        actual = first["data"]["features"][0]["geometry"]["coordinates"][0]
        self.assertAlmostEqual(actual[0], expected[0], places=6)
        self.assertAlmostEqual(actual[1], expected[1], places=6)
        self.assertEqual(response.json["source_crs"], "EPSG:9213")
        response.close()

    def test_multiple_dxf_share_crs_and_keep_independent_offsets(self):
        path = Path(self.directory.name) / "base.dxf"
        document = ezdxf.new()
        document.modelspace().add_line((0, 0), (20, 20))
        document.saveas(path)
        data = path.read_bytes()
        response = self.client.post("/api/map", data={
            "cad": [(io.BytesIO(data), "a.dxf"), (io.BytesIO(data), "b.dxf")],
            "source_crs": "EPSG:5897", "cad_offset_x": ["500000", "500100"],
            "cad_offset_y": ["2300000", "2300200"],
        })
        self.assertEqual(response.status_code, 200, response.json)
        first, second = response.json["layers"]
        self.assertEqual(first["crs"], second["crs"])
        self.assertEqual(second["offset_x"] - first["offset_x"], 100)
        self.assertEqual(second["offset_y"] - first["offset_y"], 200)

    def test_geopackage_is_not_accepted_as_background(self):
        with (python_app.ROOT / "layer_du_doan.gpkg").open("rb") as source:
            response = self.client.post("/api/map", data={
                "base": (source, "base.gpkg"), "source_crs": "EPSG:5897",
            })
        self.assertEqual(response.status_code, 400)
        self.assertIn("DXF", response.json["error"])

    def test_missing_geopackage_crs_can_be_diagnosed_and_overridden(self):
        path = Path(self.directory.name) / "unknown.gpkg"
        shutil.copyfile(python_app.ROOT / "layer_du_doan.gpkg", path)
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("UPDATE gpkg_geometry_columns SET srs_id = 0")
            connection.execute("UPDATE gpkg_contents SET srs_id = 0")
            connection.commit()
        diagnosis = gpkg_diagnostics(path)
        self.assertIsNone(diagnosis["declared_crs"])
        self.assertEqual(diagnosis["geometry_srs_id"], 5897)
        self.assertTrue(base_geojson(path, "EPSG:5897")["features"])

    def test_dxf_layer_has_geometry_without_text_labels(self):
        path = Path(self.directory.name) / "drawing.dxf"
        document = ezdxf.new()
        forward = Transformer.from_crs("EPSG:4326", "EPSG:5897", always_xy=True)
        document.modelspace().add_line(forward.transform(105, 21), forward.transform(105.001, 21.001))
        document.saveas(path)
        response = self.client.post("/api/map", data={
            "cad": (io.BytesIO(path.read_bytes()), "drawing.dxf"),
            "source_crs": "EPSG:5897",
        })
        self.assertEqual(response.status_code, 200, response.json)
        geometry = response.json["layers"][0]["data"]["features"][0]["geometry"]
        self.assertEqual(geometry["type"], "LineString")
        self.assertAlmostEqual(geometry["coordinates"][0][0], 105, places=4)
        self.assertAlmostEqual(geometry["coordinates"][0][1], 21, places=4)

    def test_cad_requires_source_crs(self):
        document = ezdxf.new()
        document.modelspace().add_line((0, 0), (1, 1))
        path = Path(self.directory.name) / "missing-crs.dxf"
        document.saveas(path)
        response = self.client.post("/api/map", data={"cad": (io.BytesIO(path.read_bytes()), "map.dxf")})
        self.assertEqual(response.status_code, 400)
        self.assertIn("EPSG", response.json["error"])


if __name__ == "__main__":
    unittest.main()
