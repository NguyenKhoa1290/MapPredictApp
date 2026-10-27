import io
import unittest

import app as python_app
from result_join import match_results, numeric_key


class ResultJoinTests(unittest.TestCase):
    def test_exact_precedes_unique_numeric_without_changing_source_keys(self):
        values = [" TP01 ", "BK002", "plain"]
        rows = [{"code": "tp01", "Y": "0"}, {"code": "2", "Y": "2"}]
        matches, report = match_results(values, rows, "code", "numeric")
        self.assertEqual([item["Y"] for item in matches], [0, 2, None])
        self.assertEqual((report["exact"], report["numeric"]), (1, 1))
        self.assertEqual(values, [" TP01 ", "BK002", "plain"])
        self.assertEqual(rows[1]["code"], "2")
        self.assertEqual(match_results(values, rows, "code")[1]["matched"], 1)

    def test_duplicate_layer_number_never_guesses_even_after_an_exact_match(self):
        matches, report = match_results(["A1", "B1"], [{"id": "A1", "Y": "0"},
                                                    {"id": "1", "Y": "2"}], "id", "numeric")
        self.assertEqual([item["Y"] for item in matches], [0, None])
        self.assertEqual(report["ambiguous"], 1)

    def test_duplicate_results_block_matching_even_when_y_agrees(self):
        for labels in [("2", "2"), ("0", "2")]:
            rows = [{"id": "a1", "Y": label} for label in labels]
            matches, report = match_results(["a1"], rows, "id", "numeric")
            self.assertIsNone(matches[0]["Y"])
            self.assertEqual(report["duplicate_result_keys"], 1)
            self.assertEqual(report["ambiguous"], 1)

    def test_duplicate_numeric_result_keys_and_duplicate_cells_remain_unfilled(self):
        for cells, rows in [(["1"], [{"id": "A1", "Y": 0}, {"id": "B1", "Y": 2}]),
                            (["same", " SAME "], [{"id": "same", "Y": 2}])]:
            matches, report = match_results(cells, rows, "id", "numeric")
            self.assertTrue(all(item["Y"] is None for item in matches))
            self.assertEqual(report["matched"], 0)

    def test_missing_invalid_and_blank_y_never_become_zero(self):
        matches, report = match_results([None, "a", "b", "c", "d"],
            [{"id": "a", "Y": ""}, {"id": "b", "Y": "3"},
             {"id": "c", "Y": "0.0"}, {"id": "d", "Y": "0"}], "id")
        self.assertEqual([item["Y"] for item in matches], [None, None, None, None, 0])
        self.assertEqual((report["missing_key"], report["no_data"], report["invalid_y"]), (1, 1, 2))

    def test_multiple_digit_groups_decimal_text_and_nonintegral_numbers(self):
        for value in ["A1B2", "1.0", 1.5, float("inf"), None, True]:
            self.assertIsNone(numeric_key(value))
        self.assertEqual(numeric_key(12.0), "12")
        self.assertEqual(numeric_key("TP0012"), "12")
        self.assertEqual(numeric_key("TP" + "0" * 5000 + "12"), "12")
        self.assertEqual(match_results(["A1B2"], [{"id": "12", "Y": 2}], "id", "numeric")[1]["matched"], 0)

    def test_report_samples_are_bounded_and_mode_is_validated(self):
        _, report = match_results(list(range(100)), [], "id")
        self.assertEqual(len(report["samples"]), 20)
        with self.assertRaises(ValueError):
            match_results([], [], "id", "nearest")

    def test_gpkg_api_numeric_results_are_request_local(self):
        data = (python_app.ROOT / "layer_du_doan.gpkg").read_bytes()
        def request(client, label):
            return client.post("/api/map", data={
                "source_crs": "EPSG:9208", "layer_join": "fid", "csv_join": "code", "join_mode": "numeric",
                "layer": (io.BytesIO(data), "grid.gpkg"),
                "result": (io.BytesIO(f"code,Y\nTP001,{label}\n".encode()), "results.csv"),
            })
        first, second = python_app.app.test_client(), python_app.app.test_client()
        for client, label in [(first, 2), (second, 0), (first, 1)]:
            response = request(client, label)
            self.assertEqual(response.status_code, 200, response.json)
            collection = response.json["layers"][0]["data"]
            self.assertEqual(collection["join_summary"]["numeric"], 1)
            matched = [item["properties"] for item in collection["features"] if item["properties"]["Y"] is not None]
            self.assertEqual([item["Y"] for item in matched], [label])
            self.assertEqual(collection["join_summary"]["samples"][0]["layer_key"], 1)
            self.assertEqual(client.get("/api/results").json["rows"], [])
            response.close()


if __name__ == "__main__":
    unittest.main()
