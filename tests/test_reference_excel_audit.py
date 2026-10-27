"""Synthetic audit tests; never open or modify user result files."""
import unittest

from tools.audit_reference_excel import audit_sheet, key, numeric


def cell(value, kind="n", formula=False):
    return {"address": "test", "raw": value, "type": kind,
            "formula": "SUM(A1:A2)" if formula else None, "has_formula": formula}


def row(code="TP01", sample="1.0", y="0.0"):
    return {"A": cell(sample), "B": cell(code, "s"), "L": cell(y),
            **{chr(67 + i): cell("1.0") for i in range(9)}}


class ReferenceExcelAuditTests(unittest.TestCase):
    def test_zero_is_valid_not_missing(self):
        data = row()
        data["H"] = cell("0.0")
        result = audit_sheet({4: data}, 4, 4)
        self.assertEqual(result["complete_rows"], 1)
        self.assertEqual(result["Y_counts"], {"0": 1, "1": 0, "2": 0})
        self.assertEqual(result["issues"], [])

    def test_missing_values_are_not_imputed(self):
        result = audit_sheet({4: {"A": cell("1"), "B": cell("BK1", "s")}}, 4, 4)
        self.assertEqual(result["complete_rows"], 0)
        self.assertEqual(len(result["issues"][0]["reasons"]), 10)
        self.assertIn("missing_Y", result["issues"][0]["reasons"])
        self.assertEqual(sum(result["Y_counts"].values()), 0)

    def test_duplicate_names_and_sample_numbers_are_separate(self):
        result = audit_sheet({4: row(), 5: row("TP02"), 6: row(" tp01 ", "3")}, 4, 6)
        self.assertEqual(result["duplicate_codes"], {"tp01": [4, 6]})
        self.assertEqual(result["duplicate_sample_numbers"], {"1": [4, 5]})

    def test_invalid_y_and_feature_are_reported(self):
        data = row(y="3")
        data["C"] = cell("not a number", "s")
        reasons = audit_sheet({4: data}, 4, 4)["issues"][0]["reasons"]
        self.assertIn("invalid_Y", reasons)
        self.assertIn("invalid_x1", reasons)
        for value in ("NaN", "Infinity", "#VALUE!", None):
            self.assertIsNone(numeric(cell(value)))
        self.assertIsNone(numeric(cell("1", "e")))

    def test_summary_cells_are_not_land_plots(self):
        result = audit_sheet({4: row(), 5: {"L": cell("100", formula=True)}}, 4, 4)
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(len(result["outside_data_after_range"]), 1)
        self.assertEqual(len(result["formula_cells"]), 1)

    def test_missing_formula_cache_is_exposed(self):
        data = row()
        data["L"] = cell(None, formula=True)
        reasons = audit_sheet({4: data}, 4, 4)["issues"][0]["reasons"]
        self.assertIn("formula_without_cached_value", reasons)
        self.assertIn("missing_Y", reasons)

    def test_numeric_and_text_identifiers_remain_distinct(self):
        self.assertEqual(key(cell("1.0")), "1")
        self.assertEqual(key(cell("001", "s")), "001")
        self.assertEqual(key(cell("1.0", "s")), "1.0")
        self.assertEqual(key(cell("TP01", "s")), "tp01")

    def test_code_gaps_do_not_renumber_samples(self):
        result = audit_sheet({4: row("TP01", "1"), 5: row("TP03", "2")}, 4, 5)
        self.assertEqual(result["numeric_code_gaps_observed_only"], [2])
        self.assertEqual(result["sample_code_mismatches_observed_only"],
                         [{"row": 5, "sample": "2", "code": "tp03"}])
        self.assertEqual(result["unique_codes"], 2)


if __name__ == "__main__":
    unittest.main()
