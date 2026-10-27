import hashlib
import math
from pathlib import Path
import tempfile
import unittest

import ezdxf

from backend.map_predict import create_app
from backend.map_predict.config import Config
from backend.map_predict.services.project_maps import join_results, label_position, project_map, read_cells, SOURCES


class ProjectMapTests(unittest.TestCase):
    @unittest.skipUnless(all((Config.PROJECT_SOURCE_FOLDER / name).is_file()
                             for name in [*(source[0] for source in SOURCES.values()), "File ex.xlsx"]),
                         "Private project sources are not distributed, run this check locally with Tailieuthamkhao")
    def test_real_sources_counts_labels_dedup_and_untouched_files(self):
        folder = Config.PROJECT_SOURCE_FOLDER
        files = [folder / source[0] for source in SOURCES.values()] + [folder / "File ex.xlsx"]
        before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in files]
        expected = {"hcm": (1695, 297, {"0": 135, "1": 162, "2": 0}),
                    "bac-kan": (400, 380, {"0": 0, "1": 12, "2": 368}),
                    "phu-quoc": (1676, 1676, {"0": 90, "1": 57, "2": 1529})}
        for slug, (total, scored, counts) in expected.items():
            data = project_map(folder, slug)
            self.assertEqual(data["counts"]["total"], total)
            self.assertEqual(data["counts"]["scored"], scored)
            self.assertEqual(data["counts"]["Y"], counts)
            features = data["collection"]["features"]
            self.assertEqual(len({feature["id"] for feature in features}), total)
            for feature in features:
                props = feature["properties"]
                self.assertEqual(props["fillOpacity"], 0 if props["Y"] is None else 0.6)
            if slug == "bac-kan":
                unscored = [feature["properties"] for feature in features if feature["properties"]["Y"] is None]
                self.assertEqual({int(item["grid_id"]) for item in unscored}, set(range(1, 21)))
            if slug == "phu-quoc":
                self.assertNotIn('1232', {feature["properties"]["grid_id"] for feature in features})
                self.assertEqual(sum(len(feature["properties"]["handles"]) for feature in features), 1734)
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).hexdigest() for path in files])

    @unittest.skipUnless(all((Config.PROJECT_SOURCE_FOLDER / name).is_file()
                             for name in [*(source[0] for source in SOURCES.values()), "File ex.xlsx"]),
                         "Private project sources are not distributed, run this check locally with Tailieuthamkhao")
    def test_readonly_api_trial_projection_and_validation(self):
        client = create_app({"TESTING": True}).test_client()
        for slug in SOURCES:
            response = client.get(f"/api/v1/projects/{slug}/map")
            self.assertEqual(response.status_code, 200)
            data = response.json["data"]
            self.assertEqual(data["source_crs"], 'EPSG:9208')
            self.assertFalse(data["crs_confirmed"])
            for feature in data["collection"]["features"]:
                for lon, lat in feature["geometry"]["coordinates"][0]:
                    self.assertTrue(math.isfinite(lon) and -180 <= lon <= 180)
                    self.assertTrue(math.isfinite(lat) and -85 <= lat <= 85)
            self.assertEqual(client.post(f"/api/v1/projects/{slug}/map").status_code, 405)
        native = client.get('/api/v1/projects/hcm/map?source_crs=').json["data"]
        self.assertEqual(native["mode"], 'native')
        self.assertGreater(native["collection"]["features"][0]["geometry"]["coordinates"][0][0][0], 600000)
        self.assertEqual(client.get('/api/v1/projects/hcm/map?source_crs=EPSG:9201').status_code, 422)
        self.assertEqual(client.get('/api/v1/projects/ai/map').status_code, 404)

    def test_numeric_join_rejects_ambiguous_codes_and_preserves_missing(self):
        cells = [{"grid_id": code} for code in ['1', '2', '3', '4', '5']]
        rows = [{"code": code, "Y": y} for code, y in [('TP01', 0), ('A2', 1), ('B2', 2), ('TP3', None), ('TP4', 1), ('TP4', 2), ('A5B2', 2)]]
        result = join_results(cells, rows, 'hcm')
        self.assertEqual([cell['Y'] for cell in result], [0, None, None, None, None])
        ambiguous = join_results([{'grid_id': 'A1'}, {'grid_id': 'B1'}], [{'code': '1', 'Y': 2}], 'hcm')
        self.assertTrue(all(cell['Y'] is None for cell in ambiguous))

    def test_mtext_placement_follows_attachment_and_rotation(self):
        document = ezdxf.new()
        msp = document.modelspace()
        for attachment, expected in [(1, (10, -4)), (5, (0, 0)), (9, (-10, 4))]:
            entity = msp.add_mtext('1', dxfattribs={'width': 20, 'char_height': 8, 'attachment_point': attachment})
            point, _ = label_position(entity)
            self.assertAlmostEqual(point.x, expected[0]); self.assertAlmostEqual(point.y, expected[1])
        entity.set_rotation(90)
        point, _ = label_position(entity)
        self.assertAlmostEqual(point.x, -4); self.assertAlmostEqual(point.y, -10)

    def test_deduplication_keeps_handles_without_nearest_label_assignment(self):
        document = ezdxf.new()
        document.layers.new('grid')
        msp = document.modelspace()
        for _ in range(2):
            msp.add_lwpolyline([(0, 0), (20, 0), (20, 20), (0, 20)], close=True, dxfattribs={'layer': 'grid'})
        msp.add_text('1', dxfattribs={'insert': (10, 10), 'layer': '0'})
        msp.add_text('1232', dxfattribs={'insert': (21, 10), 'layer': '0'})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'grid.dxf'; document.saveas(path)
            polygons, properties = read_cells(path, 'grid', 'TEXT')
        self.assertEqual(len(polygons), 1)
        self.assertEqual(len(properties[0]['handles']), 2)
        self.assertEqual(properties[0]['grid_id'], '1')


if __name__ == '__main__':
    unittest.main()
