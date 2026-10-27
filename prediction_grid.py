"""Prediction cells from modelspace closed DXF polylines and contained labels.

grid_id is a derived field from TEXT/MTEXT, not a native tenlodat attribute.
Never infer a join from drawing order, POINT elevation, or the nearest label.
"""

from collections import Counter
import math

from shapely import STRtree
from shapely.errors import GEOSException
from shapely.geometry import Point, Polygon, mapping

from cad_to_geojson import _entity_features, _read_dxf
from gis import _to_wgs84, _transformer


GRID_COLUMNS = ("grid_id", "handle", "layer")


def _key(value):
    return "" if value is None else str(value).strip().casefold()


def read_dxf_grid(path):
    document = _read_dxf(str(path))
    cells, polygons, labels = [], [], []
    warnings, ignored = Counter(), Counter()
    for entity in document.modelspace():
        kind = entity.dxftype()
        if kind in ("TEXT", "MTEXT"):
            text = entity.dxf.text if kind == "TEXT" else entity.plain_text()
            position = entity.dxf.insert
            if kind == "TEXT":
                # Aligned/right/center TEXT uses its alignment point in OCS.
                if entity.dxf.get("halign", 0) or entity.dxf.get("valign", 0):
                    position = entity.dxf.get("align_point", position)
                position = entity.ocs().to_wcs(position)
            if str(text).strip() and all(math.isfinite(v) for v in (position.x, position.y)):
                labels.append((str(text).strip(), entity.dxf.handle, Point(position.x, position.y)))
            continue
        if kind not in ("LWPOLYLINE", "POLYLINE"):
            ignored[kind] += 1
            continue
        if not entity.is_closed:
            warnings["Đường polyline hở không được coi là ô lưới"] += 1
            continue
        parts = list(_entity_features(entity, warnings=warnings))
        if len(parts) != 1 or parts[0]["geometry"]["type"] != "LineString":
            warnings["Không đọc được đường bao ô lưới"] += 1
            continue
        try:
            polygon = Polygon(parts[0]["geometry"]["coordinates"])
        except (ValueError, GEOSException):
            warnings["Ô lưới có đường bao không hợp lệ"] += 1
            continue
        if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
            warnings["Ô lưới có đường bao không hợp lệ"] += 1
            continue
        cells.append({"type": "Feature", "geometry": mapping(polygon), "properties": {
            **parts[0]["properties"], "grid_id": None, "id_source": "",
            "id_text_handle": "", "id_status": "missing",
        }})
        polygons.append(polygon)
    if not cells:
        raise ValueError("DXF không có ô lưới hợp lệ. Cần LWPOLYLINE/POLYLINE kín trong modelspace.")

    tree = STRtree(polygons)
    contained = [[] for _ in cells]
    ambiguous = set()
    for text, handle, point in labels:
        indices = tree.query(point, predicate="intersects").tolist()
        if len(indices) == 1 and polygons[indices[0]].contains(point):
            contained[indices[0]].append((text, handle))
        elif indices:
            # Boundary labels and overlapping cells must not silently get IDs.
            ambiguous.update(indices)
    for index, candidates in enumerate(contained):
        properties = cells[index]["properties"]
        if index in ambiguous or len(candidates) > 1:
            properties["id_status"] = "ambiguous"
        elif len(candidates) == 1:
            properties.update(grid_id=candidates[0][0], id_text_handle=candidates[0][1],
                              id_source="TEXT/MTEXT", id_status="valid")
    counts = Counter(_key(cell["properties"]["grid_id"]) for cell in cells
                     if cell["properties"]["id_status"] == "valid")
    for cell in cells:
        properties = cell["properties"]
        if properties["id_status"] == "valid" and counts[_key(properties["grid_id"])] > 1:
            properties["id_status"] = "duplicate"
    statuses = Counter(cell["properties"]["id_status"] for cell in cells)
    for status, label in (("missing", "Ô không có nhãn bên trong"),
                          ("ambiguous", "Ô có nhãn không xác định duy nhất"),
                          ("duplicate", "Ô có mã grid_id bị trùng")):
        if statuses[status]:
            warnings[label] += statuses[status]
    for kind, count in ignored.items():
        if kind != "POINT":
            warnings[f"{kind}: không dùng làm ô lưới DXF"] += count
    bounds = [min(p.bounds[0] for p in polygons), min(p.bounds[1] for p in polygons),
              max(p.bounds[2] for p in polygons), max(p.bounds[3] for p in polygons)]
    metadata = {
        "format": "dxf", "columns": list(GRID_COLUMNS), "declared_crs": None,
        "raw_bounds": bounds, "cell_count": len(cells), "identified_count": statuses["valid"],
        "id_status_counts": dict(statuses), "ignored_entities": dict(ignored),
        "sample_ids": [cell["properties"]["grid_id"] for cell in cells
                       if cell["properties"]["id_status"] == "valid"][:5],
        "suggested_join": "grid_id", "warnings": dict(warnings),
    }
    return {"type": "FeatureCollection", "features": cells,
            "warnings": dict(warnings), "metadata": metadata}


def dxf_grid_metadata(path):
    return read_dxf_grid(path)["metadata"]


def predicted_dxf_grid(path, rows, layer_join, csv_join, source_crs, offset_x=0, offset_y=0,
                       join_mode="exact"):
    from result_join import apply_results
    collection = read_dxf_grid(path)
    if layer_join and layer_join not in GRID_COLUMNS:
        raise ValueError(f"Không tìm thấy cột {layer_join} trong lưới DXF.")
    if rows and (not layer_join or not csv_join or csv_join not in rows[0]):
        raise ValueError("Vui lòng chọn hai cột ghép dữ liệu hợp lệ cho lưới DXF.")
    values = [cell["properties"].get(layer_join)
              if layer_join != "grid_id" or cell["properties"]["id_status"] == "valid" else None
              for cell in collection["features"]]
    apply_results(collection, rows, layer_join, csv_join, join_mode, values)
    transformer = _transformer(source_crs)
    for cell in collection["features"]:
        cell["properties"]["source_table"] = "DXF grid"
        cell["geometry"] = _to_wgs84(cell["geometry"], transformer, offset_x, offset_y)
    summary = collection["join_summary"]
    if rows and summary["unmatched"]:
        collection["warnings"]["Ô chưa khớp kết quả CSV"] = summary["unmatched"]
    if summary["invalid_y"]:
        collection["warnings"]["Ô có Y không hợp lệ"] = summary["invalid_y"]
    return collection
