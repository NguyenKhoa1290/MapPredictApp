"""Read-only CV-02 audit of the three reference project sheets (stdlib only).

Print JSON to stdout. Never save/recalculate the workbook or run the model.
Cell values retain OOXML type and raw text; blank and numeric zero are distinct.
"""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import posixpath
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Tailieuthamkhao/Giaodienfrontend/luoi/File ex.xlsx"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PROJECTS = (
    ("hcm", "data tp. HCM", 4, 300),
    ("bac-kan", "bắc kan", 4, 403),
    ("phu-quoc", "data Phú Quốc", 4, 1680),
)
FEATURES = {f"x{i}": chr(66 + i) for i in range(1, 10)}


def read_sheets(source):
    with ZipFile(source) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(t.text or "" for t in item.findall(".//m:t", NS))
                       for item in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        relationships = {item.get("Id"): item.get("Target") for item in
                         ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        for sheet in book.findall("m:sheets/m:sheet", NS):
            if sheet.get("name") not in {project[1] for project in PROJECTS}:
                continue
            target = relationships[sheet.get(f"{{{REL}}}id")]
            part = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            xml = ET.fromstring(archive.read(part))
            rows = {}
            for row in xml.findall("m:sheetData/m:row", NS):
                cells = {}
                for cell in row.findall("m:c", NS):
                    address = cell.get("r")
                    value = cell.find("m:v", NS)
                    raw = value.text if value is not None else None
                    kind = cell.get("t", "n")
                    if kind == "s" and raw is not None:
                        raw = strings[int(raw)]
                    elif kind == "inlineStr":
                        raw = "".join(t.text or "" for t in cell.findall("m:is//m:t", NS))
                    formula = cell.find("m:f", NS)
                    if raw is not None or formula is not None:
                        cells[re.sub(r"\d+$", "", address)] = {
                            "address": address, "type": kind, "raw": raw,
                            "formula": formula.text if formula is not None else None,
                            "has_formula": formula is not None,
                        }
                if cells:
                    rows[int(row.get("r"))] = cells
            yield sheet.get("name"), rows


def numeric(cell):
    if not cell or cell["type"] not in ("n", "s", "inlineStr", "str"):
        return None
    try:
        value = Decimal(cell["raw"])
        return value if value.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def key(cell):
    if not cell or cell["raw"] is None:
        return ""
    # Numeric Excel keys are typed numbers, not text codes with leading zeros.
    value = numeric(cell)
    if cell["type"] == "n" and value is not None and value == value.to_integral_value():
        return str(int(value))
    return cell["raw"].strip().casefold()


def audit_sheet(rows, first, last):
    names, samples, numeric_parts = defaultdict(list), defaultdict(list), defaultdict(list)
    issues, counts, missing_features = [], Counter(), Counter()
    types, feature_values = Counter(), {field: Counter() for field in FEATURES}
    examples, formulas, errors, sample_code_mismatches = [], [], [], []
    for number, cells in rows.items():
        for cell in cells.values():
            if cell["has_formula"]:
                formulas.append(cell)
            if cell["type"] == "e":
                errors.append(cell)
    for number in range(first, last + 1):
        cells = rows.get(number, {})
        problems = []
        name = key(cells.get("B"))
        sample = key(cells.get("A"))
        if name:
            names[name].append(number)
            types[cells["B"]["type"]] += 1
            groups = re.findall(r"\d+", name)
            if len(groups) == 1:
                numeric_parts[str(int(groups[0]))].append(number)
                if sample and sample != str(int(groups[0])):
                    sample_code_mismatches.append({"row": number, "sample": sample, "code": name})
            else:
                problems.append("code_not_single_numeric_group")
        else:
            problems.append("missing_code")
        if sample:
            samples[sample].append(number)
        else:
            problems.append("missing_sample_number")
        for field, col in FEATURES.items():
            cell = cells.get(col)
            value = numeric(cell)
            if cell is None or cell["raw"] is None or not cell["raw"].strip():
                missing_features[field] += 1
                problems.append(f"missing_{field}")
            elif value is None:
                problems.append(f"invalid_{field}")
            else:
                feature_values[field][str(value.normalize())] += 1
        y = numeric(cells.get("L"))
        if "L" not in cells or cells["L"]["raw"] is None or not cells["L"]["raw"].strip():
            problems.append("missing_Y")
        elif y not in (Decimal(0), Decimal(1), Decimal(2)):
            problems.append("invalid_Y")
        else:
            counts[str(int(y))] += 1
        if any(cell["has_formula"] and cell["raw"] is None for cell in cells.values()):
            problems.append("formula_without_cached_value")
        if problems:
            issues.append({"row": number, "code": cells.get("B"), "reasons": problems})
        if len(examples) < 3 or number == last:
            examples.append({"row": number, "sample": cells.get("A"), "code": cells.get("B"),
                             "Y": cells.get("L")})
    duplicate = lambda groups: {value: numbers for value, numbers in groups.items() if len(numbers) > 1}
    numbers = sorted(int(value) for value in numeric_parts)
    outside = [{"row": number, "cells": cells} for number, cells in rows.items()
               if number > last]
    return {
        "data_range": f"A{first}:L{last}", "row_count": last - first + 1,
        "nonempty_rows_scanned": len(rows), "unique_codes": len(names),
        "code_types": dict(types), "duplicate_codes": duplicate(names),
        "duplicate_sample_numbers": duplicate(samples),
        "duplicate_numeric_parts_observed_only": duplicate(numeric_parts),
        "numeric_code_extent_observed_only": [numbers[0], numbers[-1]] if numbers else None,
        "numeric_code_gaps_observed_only": sorted(set(range(numbers[0], numbers[-1] + 1))
                                                 - set(numbers)) if numbers else [],
        "sample_code_mismatches_observed_only": sample_code_mismatches,
        "Y_counts": {str(i): counts[str(i)] for i in range(3)},
        "missing_features": dict(missing_features),
        "feature_values": {field: dict(values) for field, values in feature_values.items()},
        "complete_rows": last - first + 1 - len(issues), "issues": issues,
        "examples": examples, "formula_cells": formulas, "excel_errors": errors,
        "outside_data_after_range": outside,
    }


def audit(source=SOURCE):
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    sheets = dict(read_sheets(source))
    results = {}
    for project, name, first, last in PROJECTS:
        if name not in sheets:
            raise ValueError(f"Missing required sheet: {name}")
        rows = sheets[name]
        if [rows[3][col]["raw"] for col in FEATURES.values()] != list(FEATURES):
            raise ValueError(f"Feature header layout changed: {name}")
        results[project] = {"sheet": name, **audit_sheet(rows, first, last)}
    after = hashlib.sha256(source.read_bytes()).hexdigest()
    if before != after:
        raise RuntimeError("Workbook changed during read-only audit")
    return {"source": source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else str(source),
            "sha256": before, "source_unchanged": True, "projects": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    args = parser.parse_args()
    print(json.dumps(audit(args.source.resolve()), ensure_ascii=True, indent=2))
