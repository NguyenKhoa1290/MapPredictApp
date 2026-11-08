"""Read project workbook cells without modifying source files (stdlib only)."""
from decimal import Decimal, InvalidOperation
import posixpath
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

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
