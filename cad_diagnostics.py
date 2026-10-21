"""Conservative, read-only recovery of CAD block translations.

A recoverable INSERT transform is evidence for a proposed placement, not proof
that the block coordinates or the user-selected CRS are georeferenced correctly.
"""

import math

from ezdxf import DXFError
from ezdxf.math import Matrix44
from shapely.geometry import MultiPoint

from cad_to_geojson import _entity_features, _read_dxf
from gis import _transformer, parse_source_crs


def _bounds(points):
    return (min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points))


def cad_diagnostics(path, source_crs):
    crs = parse_source_crs(source_crs)
    result = {"source_crs": crs.to_string(), "status": "unavailable",
              "raw_bounds": None, "candidate": None}

    def finish(message, status="unavailable"):
        return {**result, "status": status, "message": message}

    if not crs.is_projected or not crs.axis_info or any(
            not math.isclose(axis.unit_conversion_factor, 1) for axis in crs.axis_info[:2]):
        return finish("Chọn EPSG nguồn dạng tọa độ phẳng, đơn vị mét để phân tích độ dịch.")
    transformer = _transformer(crs)
    area = crs.area_of_use
    if area is None:
        return finish("EPSG này không có phạm vi sử dụng để kiểm tra vị trí đề xuất.")

    def in_area(bounds):
        for x in (bounds[0], bounds[2]):
            for y in (bounds[1], bounds[3]):
                lon, lat = transformer.transform(x, y)
                if not (math.isfinite(lon) and math.isfinite(lat)
                        and area.west <= lon <= area.east
                        and area.south <= lat <= area.north):
                    return False
        return True

    try:
        document = _read_dxf(str(path))
    except (DXFError, UnicodeError) as error:
        raise ValueError("Không đọc được cấu trúc DXF để phân tích độ dịch.") from error
    candidates = []
    affine_blocks = []
    inspected = 0
    vertex_count = 0
    incomplete = False

    def inspect(points, matrix, block_path):
        # Small symbol definitions and local drawing coordinates are not anchors.
        if len(points) < 4:
            return
        bounds = _bounds(points)
        if max(abs(v) for v in bounds) < 100000 or not in_area(bounds):
            return
        distinct = set(points)
        if len(distinct) < 4 or MultiPoint(list(distinct)).convex_hull.area < 1:
            return
        for vector in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            actual = matrix.transform_direction(vector)
            if any(abs(actual[i] - vector[i]) > 1e-9 for i in range(3)):
                affine_blocks.append(" / ".join(block_path))
                return
        origin = matrix.transform((0, 0, 0))
        dx, dy = -origin.x, -origin.y
        if math.hypot(dx, dy) < 100000:
            return
        residual = 0
        for x, y in points:
            placed = matrix.transform((x, y, 0))
            residual = max(residual, math.hypot(placed.x + dx - x, placed.y + dy - y))
        if residual <= 1e-5:
            candidates.append({"offset_x": dx, "offset_y": dy,
                               "block": " / ".join(block_path),
                               "support_points": len(distinct), "max_residual_m": residual})

    def walk(entities, parent, names=()):
        nonlocal inspected, vertex_count, incomplete
        points = []
        for entity in entities:
            inspected += 1
            if inspected > 100000:
                raise ValueError("DXF quá phức tạp để phân tích tự động (trên 100.000 đối tượng).")
            if entity.dxftype() == "INSERT":
                name = entity.dxf.name
                block = document.blocks.get(name)
                # Match the renderer's supported single INSERT case conservatively.
                if (block is None or name in names or len(names) >= 20
                        or entity.dxf.row_count > 1 or entity.dxf.column_count > 1):
                    incomplete = True
                    continue
                matrix = entity.matrix44()
                combined = matrix @ parent
                child_points = walk(block, combined, names + (name,))
                inspect(child_points, combined, names + (name,))
                points.extend((p.x, p.y) for p in matrix.transform_vertices(
                    (x, y, 0) for x, y in child_points))
            elif entity.dxftype() in ("LINE", "LWPOLYLINE", "POLYLINE"):
                for feature in _entity_features(entity):
                    coords = feature["geometry"]["coordinates"]
                    vertex_count += len(coords)
                    if vertex_count > 500000:
                        raise ValueError("DXF có quá nhiều đỉnh để phân tích tự động (trên 500.000).")
                    if not all(math.isfinite(v) for p in coords for v in p):
                        raise ValueError("DXF có tọa độ không hữu hạn; không thể đề xuất độ dịch.")
                    points.extend(tuple(p) for p in coords)
        return points

    points = walk(document.modelspace(), Matrix44())
    if incomplete:
        return finish("Có block lặp, thiếu, tham chiếu vòng hoặc quá nhiều cấp; không đủ bằng chứng để dịch toàn bộ layer.")
    if not points:
        return finish("Không tìm thấy hình học đường được hỗ trợ để đối chiếu.")
    bounds = _bounds(points)
    result["raw_bounds"] = list(bounds)
    if in_area(bounds):
        return finish("Hình học đã nằm trong phạm vi EPSG đã chọn; không đề xuất cộng thêm độ dịch.", "already_positioned")
    if max(abs(v) for v in bounds) >= 100000:
        return finish("Hình học không thuần tọa độ cục bộ hoặc có dữ liệu trộn; không đề xuất một độ dịch chung.")
    if affine_blocks:
        return finish("Block tọa độ lớn có phép xoay, co giãn hoặc phản chiếu; chỉ cộng X/Y sẽ không đúng. Cần nắn chỉnh bằng điểm mốc hoặc QGIS.", "affine_required")
    if not candidates:
        return finish("Không tìm thấy block giữ tọa độ gốc đủ bằng chứng. Cần nhập độ dịch theo điểm mốc hoặc chỉnh trong QGIS.")
    best = max(candidates, key=lambda item: item["support_points"])
    if any(math.hypot(item["offset_x"] - best["offset_x"],
                      item["offset_y"] - best["offset_y"]) > 0.001 for item in candidates):
        return finish("Các block gợi ý nhiều độ dịch khác nhau; không thể chọn tự động một độ dịch cho cả layer.", "ambiguous")
    dx, dy = best["offset_x"], best["offset_y"]
    shifted = (bounds[0] + dx, bounds[1] + dy, bounds[2] + dx, bounds[3] + dy)
    if not in_area(shifted):
        return finish("Độ dịch từ block không đặt toàn bộ layer trong phạm vi EPSG đã chọn; cần kiểm tra lại.")
    preview = transformer.transform_bounds(*shifted, densify_pts=21)
    longitude, latitude = transformer.transform((shifted[0] + shifted[2]) / 2,
                                               (shifted[1] + shifted[3]) / 2)
    result["candidate"] = {
        "offset_x": dx, "offset_y": dy,
        "blocks": list(dict.fromkeys(item["block"] for item in candidates)),
        "support_points": best["support_points"],
        "max_residual_m": max(item["max_residual_m"] for item in candidates),
        "preview_bounds": list(preview), "longitude": longitude, "latitude": latitude,
    }
    return finish("Tìm được độ dịch ngược từ phép chèn block. Đây là đề xuất, không xác nhận EPSG hay độ khớp thực địa. Hãy xem trước rồi xác nhận.", "suggested")
