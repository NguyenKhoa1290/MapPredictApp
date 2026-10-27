"""Read-only project grids and existing workbook labels. Never execute a model."""
from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
import math
from pathlib import Path
import re

import ezdxf
from pyproj import Transformer
from shapely import STRtree, normalize
from shapely.geometry import Point, Polygon, mapping
from shapely.ops import transform

from cad_to_geojson import _entity_features
from gis import source_crs_options
from tools.audit_reference_excel import PROJECTS, key, numeric, read_sheets

PALETTE = {0: "#ff0000", 1: "#ffa500", 2: "#008000"}
SOURCES = {
    "hcm": ("luoi_hcm.dxf", "DTL-1D", "MTEXT"),
    "bac-kan": ("bắc kan.dxf", "00.Ranh gioi", "MTEXT"),
    "phu-quoc": ("phú quốc.dxf", "Docao", "TEXT"),
}


def numeric_key(value):
    match = re.fullmatch(r"[^0-9]*([0-9]+)[^0-9]*", value)
    return str(int(match[1])) if match else None


def label_position(entity):
    """Center of the explicit MTEXT reference box for plain one-line numeric labels.

    Not a nearest-label correction. Unsupported formatting is left unassigned.
    The caller also requires the insertion anchor to touch that same cell.
    Reference width is a layout box, not the rendered glyph extent.
    """
    insert = entity.dxf.insert
    if entity.dxftype() == "TEXT":
        return Point(insert.x, insert.y), None
    if not re.fullmatch(r"\d+", entity.text.strip()) or entity.dxf.width <= 0:
        return None, None
    width, height = entity.dxf.width, entity.dxf.char_height
    attachment = entity.dxf.attachment_point - 1
    if not 0 <= attachment < 9 or height <= 0:
        return None, None
    left = -(attachment % 3) * width / 2
    top = (attachment // 3) * height / 2
    angle = math.radians(entity.get_rotation())

    def world(x, y):
        return (insert.x + x * math.cos(angle) - y * math.sin(angle),
                insert.y + x * math.sin(angle) + y * math.cos(angle))

    box = Polygon([world(left, top), world(left + width, top),
                   world(left + width, top - height), world(left, top - height)])
    return box.centroid, box


def read_cells(path, grid_layer, label_kind):
    document = ezdxf.readfile(path)
    polygons, properties, groups = [], [], {}
    for entity in document.modelspace():
        if entity.dxftype() != "LWPOLYLINE" or entity.dxf.layer != grid_layer or not entity.is_closed:
            continue
        parts = list(_entity_features(entity, warnings=Counter()))
        if len(parts) != 1 or parts[0]["geometry"]["type"] != "LineString":
            raise ValueError("Đường bao lưới không được hỗ trợ.")
        polygon = Polygon(parts[0]["geometry"]["coordinates"])
        if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
            raise ValueError("Đường bao lưới không hợp lệ.")
        fingerprint = normalize(polygon).wkb
        if fingerprint in groups:
            properties[groups[fingerprint]]["handles"].append(entity.dxf.handle)
            continue
        groups[fingerprint] = len(polygons)
        polygons.append(polygon)
        properties.append({"handles": [entity.dxf.handle], "grid_id": None, "label_status": "missing"})
    if not polygons:
        raise ValueError("Không tìm thấy ô lưới dự án.")
    tree, assigned = STRtree(polygons), defaultdict(list)
    for entity in document.modelspace():
        if entity.dxftype() != label_kind or entity.dxf.layer != "0":
            continue
        text = entity.plain_text().strip() if label_kind == "MTEXT" else entity.dxf.text.strip()
        if not re.fullmatch(r"\d+", text):
            continue
        point, box = label_position(entity)
        if point is None:
            continue
        candidates = tree.query(point, predicate="within").tolist()
        if len(candidates) != 1:
            continue
        index = candidates[0]
        # Tolerance only for floating-point insertion edges, never a nearest-cell search.
        tolerance = max(abs(v) for v in polygons[index].bounds) * 1e-12
        insert = entity.dxf.insert
        if box is not None and not polygons[index].buffer(tolerance).covers(Point(insert.x, insert.y)):
            continue
        assigned[index].append((text, entity.dxf.handle))
    code_counts = Counter(labels[0][0] for labels in assigned.values() if len(labels) == 1)
    for index, labels in assigned.items():
        if len(labels) == 1 and code_counts[labels[0][0]] == 1:
            properties[index].update(grid_id=labels[0][0], label_handle=labels[0][1], label_status="valid")
        else:
            properties[index]["label_status"] = "ambiguous"
    return polygons, properties


def result_rows(folder, slug):
    _, sheet, first, last = next(item for item in PROJECTS if item[0] == slug)
    rows = dict(read_sheets(folder / "File ex.xlsx"))[sheet]
    output = []
    for number in range(first, last + 1):
        cells = rows.get(number, {})
        code, value = key(cells.get("B")), numeric(cells.get("L"))
        output.append({"code": code, "Y": int(value) if value in (0, 1, 2) else None})
    return output


def join_results(properties, rows, slug):
    exact, numbers = defaultdict(list), defaultdict(list)
    cell_exact, cell_numbers = Counter(), Counter()
    for row in rows:
        exact[row["code"]].append(row)
        number = numeric_key(row["code"])
        if number is not None:
            numbers[number].append(row)
    for item in properties:
        if item["grid_id"] is not None:
            code = item["grid_id"].strip().casefold()
            cell_exact[code] += 1
            cell_numbers[numeric_key(code)] += 1
    for item in properties:
        code = (item["grid_id"] or "").strip().casefold()
        number = numeric_key(code)
        matches = exact.get(code, []) if cell_exact[code] == 1 else []
        if not matches and number is not None and cell_numbers[number] == 1:
            matches = numbers.get(number, [])
        row = matches[0] if len(matches) == 1 else None
        y = row["Y"] if row else None
        if slug == "bac-kan" and number is not None and 1 <= int(number) <= 20:
            y = None
        if slug == "phu-quoc" and number == "1232":
            y = None
        item.update(code=row["code"] if row else None, Y=y,
                    fillColor=PALETTE.get(y), fillOpacity=0.6 if y is not None else 0)
    return properties


@lru_cache(maxsize=6)
def _load(folder, slug, grid_stamp, workbook_stamp):
    filename, layer, kind = SOURCES[slug]
    polygons, properties = read_cells(Path(folder) / filename, layer, kind)
    return polygons, join_results(properties, result_rows(Path(folder), slug), slug)


def project_map(folder, slug, source_crs=None):
    folder = Path(folder)
    grid = folder / SOURCES[slug][0]
    workbook = folder / "File ex.xlsx"
    polygons, properties = _load(str(folder.resolve()), slug,
                               (grid.stat().st_mtime_ns, grid.stat().st_size),
                               (workbook.stat().st_mtime_ns, workbook.stat().st_size))
    choices = source_crs_options()
    if source_crs and source_crs not in {item["code"] for item in choices}:
        raise ValueError("Chọn hệ tọa độ trong danh sách được hỗ trợ.")
    if source_crs:
        converter = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
        polygons = [transform(lambda x, y: converter.transform(x, y, errcheck=True), polygon) for polygon in polygons]
        if any(not all(math.isfinite(v) for v in p.bounds) or p.bounds[0] < -180 or p.bounds[2] > 180
               or p.bounds[1] < -85 or p.bounds[3] > 85 for p in polygons):
            raise ValueError("Tọa độ sau chuyển đổi nằm ngoài phạm vi bản đồ.")
    counts = Counter(item["Y"] for item in properties)
    return {"project_id": slug, "mode": "geographic" if source_crs else "native",
            "source_crs": source_crs, "crs_confirmed": False, "crs_options": choices,
            "collection": {"type": "FeatureCollection", "features": [
                {"type": "Feature", "id": item["handles"][0], "geometry": mapping(polygon),
                 "properties": deepcopy(item)} for polygon, item in zip(polygons, properties)]},
            "counts": {"total": len(properties), "scored": sum(counts[y] for y in PALETTE),
                       "unscored": counts[None], "Y": {str(y): counts[y] for y in PALETTE}}}
