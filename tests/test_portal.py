"""New app factory/public API tests, with no model or result writes."""
import json
from pathlib import Path
import tempfile
import unittest

from backend.map_predict import create_app


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_factories_are_separate_and_default_has_no_legacy_api(self):
        second = create_app({"TESTING": True, "MAX_CONTENT_LENGTH": 123})
        self.assertIsNot(self.app, second)
        self.assertNotEqual(self.app.config["MAX_CONTENT_LENGTH"], second.config["MAX_CONTENT_LENGTH"])
        self.assertEqual(self.client.get("/").location, "/portal/")
        self.assertEqual(self.client.get("/api/results").status_code, 404)
        self.assertEqual(self.client.post("/api/predict").status_code, 404)
        self.assertFalse(self.client.get("/api/v1/site-content").json["data"]["legacy_available"])

    def test_public_catalog_and_content_contract(self):
        content = self.client.get("/api/v1/site-content")
        self.assertEqual(content.status_code, 200)
        self.assertEqual(content.json["meta"]["request_id"], content.headers["X-Request-ID"])
        self.assertEqual(len(content.json["data"]["visions"]), 3)
        self.assertEqual(len(content.json["data"]["members"]), 4)
        projects = self.client.get("/api/v1/projects").json["data"]
        self.assertEqual([item["id"] for item in projects], ["hcm", "bac-kan", "phu-quoc", "ai"])
        self.assertNotIn(".dxf", json.dumps(projects))
        self.assertNotIn("sha256", json.dumps(projects))

    def test_project_metadata_indicates_map_preview(self):
        detail = self.client.get("/api/v1/projects/phu-quoc")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json["data"]["status"], "preview")
        self.assertEqual([row["color"] for row in detail.json["data"]["legend"]],
                         ["#ff0000", "#ffa500", "#008000"])
        with tempfile.TemporaryDirectory() as directory:
            client = create_app({"TESTING": True, "PROJECT_SOURCE_FOLDER": Path(directory)}).test_client()
            response = client.get("/api/v1/projects/phu-quoc/map")
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json["error"]["code"], "PROJECT_NOT_READY")

    def test_unknown_api_and_assets_do_not_return_spa_html(self):
        for url in ("/api/v1/unknown", "/api/v1/projects/unknown", "/api/v1/projects/unknown/map",
                    "/portal/assets/missing.js", "/portal/unknown", "/portal/projects/unknown",
                    "/portal/assets/../../config/projects.json"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404, url)
            self.assertTrue(response.is_json, url)

    def test_frontend_missing_build_and_direct_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app({"TESTING": True, "FRONTEND_DIST": Path(directory)})
            client = app.test_client()
            self.assertEqual(client.get("/portal").location, "/portal/")
            for url in ("/portal/", "/portal/projects", "/portal/assessment", "/portal/assessment/csv", "/portal/projects/bac-kan"):
                response = client.get(url)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json["error"]["code"], "FRONTEND_NOT_BUILT")

    def test_public_routes_reject_upload_methods(self):
        self.assertEqual(self.client.post("/api/v1/projects").status_code, 405)
        self.assertEqual(self.client.post("/api/v1/site-content").status_code, 405)

    def test_refresh_routes_and_assets_are_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text('<!doctype html><div id="root"></div>', encoding="utf-8")
            (root / "assets").mkdir()
            (root / "assets" / "fixture.js").write_text('console.log("fixture");', encoding="utf-8")
            client = create_app({"TESTING": True, "FRONTEND_DIST": root}).test_client()
            for url in ("/portal/", "/portal/projects", "/portal/assessment", "/portal/projects/hcm"):
                with client.get(url) as response:
                    self.assertEqual(response.status_code, 200, url)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertIn(b'id="root"', response.data)
            with client.get("/portal/assets/fixture.js") as response:
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'console.log', response.data)
                self.assertIn("immutable", response.headers["Cache-Control"])
            self.assertEqual(client.get("/portal/assets/missing.js").status_code, 404)


if __name__ == "__main__":
    unittest.main()
