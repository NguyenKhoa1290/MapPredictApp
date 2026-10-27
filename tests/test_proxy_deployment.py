import io
import tempfile
from pathlib import Path
import unittest

import app as legacy_app
from backend.map_predict import create_app


class ProxyDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "PROXY_HOPS": 1}, legacy_blueprint=legacy_app.legacy)
        self.client = self.app.test_client()

    def test_https_origin_through_tunnel_is_accepted_by_both_apis(self):
        headers = {"Origin": "https://danhgiaquyhoach.top", "X-Forwarded-Proto": "https"}
        for path in ("/api/preview-csv", "/api/v1/predictions/preview"):
            response = self.client.post(path, base_url="http://danhgiaquyhoach.top", headers=headers,
                data={"csv": (io.BytesIO(b'id,x1\nA1,1\n'), "input.csv")})
            self.assertEqual(response.status_code, 200, response.json)

    def test_foreign_websites_cannot_submit_jobs_to_either_api(self):
        for path in ("/api/preview-csv", "/api/v1/predictions/preview"):
            response = self.client.post(path, base_url="http://danhgiaquyhoach.top",
                headers={"Origin": "https://foreign.example", "X-Forwarded-Proto": "https"},
                data={"csv": (io.BytesIO(b'id,x1\nA1,1\n'), "input.csv")})
            self.assertEqual(response.status_code, 403, response.json)

    def test_missing_external_project_mount_returns_not_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            client = create_app({"TESTING": True, "PROJECT_SOURCE_FOLDER": Path(folder)}).test_client()
            self.assertEqual(client.get("/api/v1/projects/hcm/map").status_code, 409)


if __name__ == "__main__":
    unittest.main()
