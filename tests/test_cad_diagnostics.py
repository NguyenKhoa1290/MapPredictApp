import io
import tempfile
import unittest
from pathlib import Path

import ezdxf
from ezdxf.math import Matrix44

from app import app
from cad_diagnostics import cad_diagnostics


ANCHOR = [(515100, 2402100), (515300, 2402100),
          (515300, 2402300), (515100, 2402300)]


class CadDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "arbitrary-name.dxf"
        self.client = app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def translated(self, rotation=0, scale=1, base=(0, 0), outer=(25, 50)):
        document = ezdxf.new()
        block = document.blocks.new("original-geometry", base_point=base)
        block.add_lwpolyline(ANCHOR, close=True)
        container = document.blocks.new("nested-container")
        # Keep the final drawing local even when testing a rotated/scaled INSERT.
        matrix = Matrix44.scale(scale, scale, 1) @ Matrix44.z_rotate(rotation * 3.141592653589793 / 180)
        transformed = matrix.transform((ANCHOR[0][0] - base[0], ANCHOR[0][1] - base[1], 0))
        container.add_blockref(block.name, (2100 - transformed.x, 1100 - transformed.y),
                               dxfattribs={"rotation": rotation, "xscale": scale, "yscale": scale})
        document.modelspace().add_blockref(container.name, outer)
        return document

    def diagnose(self, document):
        document.saveas(self.path)
        original = self.path.read_bytes()
        result = cad_diagnostics(self.path, "EPSG:9208")
        self.assertEqual(self.path.read_bytes(), original)
        return result

    def test_nested_translation_with_nonzero_block_base_is_recovered(self):
        result = self.diagnose(self.translated(base=(13, 17)))
        self.assertEqual(result["status"], "suggested", result)
        candidate = result["candidate"]
        self.assertAlmostEqual(candidate["offset_x"], 512975, places=6)
        self.assertAlmostEqual(candidate["offset_y"], 2400950, places=6)
        self.assertEqual(candidate["support_points"], 4)
        self.assertLess(candidate["max_residual_m"], 1e-5)
        self.assertTrue(104 < candidate["longitude"] < 106)
        self.assertTrue(21 < candidate["latitude"] < 23)
        self.assertEqual(candidate["blocks"], ["nested-container / original-geometry"])
        bounds = candidate["preview_bounds"]
        self.assertLess(bounds[0], candidate["longitude"])
        self.assertLess(candidate["longitude"], bounds[2])

    def test_rotation_and_scale_are_not_misreported_as_translation(self):
        for rotation, scale in ((30, 1), (0, 2), (0, -1)):
            with self.subTest(rotation=rotation, scale=scale):
                result = self.diagnose(self.translated(rotation=rotation, scale=scale))
                self.assertEqual(result["status"], "affine_required", result)
                self.assertIsNone(result["candidate"])

    def test_conflicting_anchor_blocks_require_manual_choice(self):
        document = self.translated()
        block = document.blocks.new("other-original")
        block.add_lwpolyline(ANCHOR, close=True)
        document.modelspace().add_blockref(block.name, (-513500, -2401000))
        result = self.diagnose(document)
        self.assertEqual(result["status"], "ambiguous", result)
        self.assertIsNone(result["candidate"])

    def test_local_coordinates_without_anchor_are_not_guessed(self):
        document = ezdxf.new()
        document.modelspace().add_lwpolyline([(0, 0), (20, 0), (20, 20), (0, 20)], close=True)
        result = self.diagnose(document)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["candidate"])

    def test_already_projected_drawing_has_no_offset_proposal(self):
        document = ezdxf.new()
        document.modelspace().add_lwpolyline(ANCHOR, close=True)
        result = self.diagnose(document)
        self.assertEqual(result["status"], "already_positioned")
        self.assertIsNone(result["candidate"])

    def test_mixed_local_and_projected_data_is_not_shifted_globally(self):
        document = self.translated()
        document.modelspace().add_lwpolyline(ANCHOR, close=True)
        result = self.diagnose(document)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["candidate"])

    def test_collinear_or_tiny_symbol_cannot_be_anchor(self):
        for points in ([ANCHOR[0], ANCHOR[1]],
                       [(515100 + i, 2402100 + i) for i in range(4)],
                       [(515100, 2402100), (515100.1, 2402100),
                        (515100.1, 2402100.1), (515100, 2402100.1)]):
            with self.subTest(points=points):
                document = ezdxf.new()
                block = document.blocks.new("symbol")
                block.add_lwpolyline(points, close=True)
                document.modelspace().add_blockref(block.name, (-513000, -2401000))
                self.assertIsNone(self.diagnose(document)["candidate"])

    def test_missing_and_recursive_blocks_do_not_produce_partial_proposal(self):
        for recursive in (True, False):
            document = self.translated()
            if recursive:
                block = document.blocks.new("recursive")
                block.add_blockref("recursive", (0, 0))
                document.modelspace().add_blockref("recursive", (0, 0))
            else:
                document.modelspace().add_blockref("missing-block", (0, 0))
            result = self.diagnose(document)
            self.assertEqual(result["status"], "unavailable")
            self.assertIsNone(result["candidate"])

    def test_geographic_crs_not_interpreted_as_metre_offset(self):
        self.translated().saveas(self.path)
        self.assertIsNone(cad_diagnostics(self.path, "EPSG:4326")["candidate"])

    def test_api_only_proposes_and_existing_map_uses_offset_after_confirmation(self):
        self.translated().saveas(self.path)
        original = self.path.read_bytes()
        with io.BytesIO(original) as stream:
            response = self.client.post("/api/cad-diagnostics", data={
                "cad": (stream, self.path.name), "source_crs": "EPSG:9208"})
        self.assertEqual(response.status_code, 200, response.json)
        proposal = response.json["candidate"]
        self.assertIsNotNone(proposal)
        self.assertEqual(self.path.read_bytes(), original)
        with io.BytesIO(original) as stream:
            response = self.client.post("/api/map", data={
                "cad": (stream, self.path.name), "source_crs": "EPSG:9208",
                "cad_offset_x": str(proposal["offset_x"]),
                "cad_offset_y": str(proposal["offset_y"]),
            })
        self.assertEqual(response.status_code, 200, response.json)
        lon, lat = response.json["layers"][0]["data"]["features"][0]["geometry"]["coordinates"][0]
        self.assertTrue(104 < lon < 106 and 21 < lat < 23)

    def test_api_rejects_missing_crs_file_and_wrong_extension(self):
        for data in ({}, {"source_crs": "EPSG:0"}, {"source_crs": "EPSG:9208"},
                     {"source_crs": "EPSG:9208", "cad": (io.BytesIO(b"text"), "wrong.gpkg")}):
            response = self.client.post("/api/cad-diagnostics", data=data)
            self.assertEqual(response.status_code, 400, response.json)

    def test_broken_dxf_returns_validation_error(self):
        response = self.client.post("/api/cad-diagnostics", data={
            "source_crs": "EPSG:9208", "cad": (io.BytesIO(b"not a drawing"), "broken.dxf")})
        self.assertEqual(response.status_code, 400, response.json)

    def test_repeated_insert_is_not_used_as_partial_evidence(self):
        document = self.translated()
        document.modelspace().query("INSERT")[0].dxf.row_count = 2
        self.assertIsNone(self.diagnose(document)["candidate"])


if __name__ == "__main__":
    unittest.main()
