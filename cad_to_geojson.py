"""
Fallback CAD reader for MapPredictApp.

Reads DXF with ezdxf and prints a GeoJSON FeatureCollection. This is used when
netDxf cannot detect a DXF version, for example "DXF file version not supported:
Unknown".
"""
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO

import ezdxf
from ezdxf import recover
from ezdxf.colors import aci2rgb, int2rgb
from ezdxf.path import make_path, from_hatch
from shapely.geometry import Polygon, mapping
from shapely.errors import GEOSException


def _error(message, exit_code=1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(exit_code)


def _xy(point):
    return [float(point[0]), float(point[1])]


def read_assistant_attributes(entity):
    """Custom CAD properties stored as bounded, portable XDATA text chunks."""
    if not entity.has_xdata('MAP_PREDICT'):
        return {}
    try:
        text = ''.join(tag.value for tag in entity.get_xdata('MAP_PREDICT') if tag.code == 1000)
        value = json.loads(text[:16384])
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError, ezdxf.DXFError):
        return {}


def _feature(coords, layer):
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {"layer": layer or ""},
    }


def _entity_features(entity, *, inherited_layer=None, inherited_color=None,
                     block_path=(), warnings=None):
    entity_type = entity.dxftype()
    layer = getattr(entity.dxf, "layer", "")
    if layer == "0" and inherited_layer:
        layer = inherited_layer
    color = inherited_color or "#ffffff"
    aci = entity.dxf.get("color", 256)
    true_color = entity.dxf.get("true_color")
    if true_color is not None:
        color = int2rgb(true_color).to_hex()
    elif 1 <= abs(aci) <= 255:
        color = aci2rgb(abs(aci)).to_hex()
    elif aci == 256 and entity.doc is not None:
        source_layer = entity.doc.layers.get(layer)
        if source_layer is not None:
            color = source_layer.rgb
            color = ("#%02x%02x%02x" % color if color else
                     aci2rgb(abs(source_layer.color) or 7).to_hex())
    source_entity = getattr(entity, "origin_of_copy", None) or entity
    properties = {"layer": layer, "entity_type": entity_type, "color": color,
                  "handle": source_entity.dxf.get("handle") or "",
                  "block": " / ".join(block_path),
                  "linetype": entity.dxf.get("linetype", "BYLAYER")}
    properties.update({'attr:' + key: value for key, value in read_assistant_attributes(source_entity).items()})

    def warn(reason):
        if warnings is not None:
            key = f"{entity_type}: {reason}"
            warnings[key] = warnings.get(key, 0) + 1

    def feature(geometry):
        return {"type": "Feature", "geometry": geometry, "properties": dict(properties)}

    if entity_type == "LINE":
        yield feature({"type": "LineString", "coordinates": [_xy(entity.dxf.start), _xy(entity.dxf.end)]})
        return

    if entity_type == "POINT":
        yield feature({"type": "Point", "coordinates": _xy(entity.dxf.location)})
        return

    if entity_type == "LEADER":
        points = [_xy(point) for point in entity.vertices]
        if len(points) >= 2:
            yield feature({"type": "LineString", "coordinates": points})
        return

    if entity_type in ("LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE", "HELIX"):
        try:
            path = make_path(entity)
            for sub_path in path.sub_paths():
                points = [_xy(point) for point in sub_path.flattening(0.1, segments=8)]
                if len(points) >= 2:
                    yield feature({"type": "LineString", "coordinates": points})
        except (ValueError, TypeError, AttributeError, ezdxf.DXFError):
            warn("không đọc được đường hình học")
        return

    if entity_type in ("SOLID", "TRACE", "3DFACE"):
        points = [_xy(point) for point in entity.wcs_vertices(close=True)]
        if len(points) >= 4:
            yield feature({"type": "Polygon", "coordinates": [points]})
        return

    if entity_type in ("HATCH", "MPOLYGON"):
        try:
            # Even/odd rings preserve holes instead of painting over them.
            area = Polygon()
            for path in from_hatch(entity):
                for sub_path in path.sub_paths():
                    points = [_xy(point) for point in sub_path.flattening(0.1, segments=8)]
                    if len(points) >= 3:
                        polygon = Polygon(points)
                        area = area.symmetric_difference(polygon if polygon.is_valid else polygon.buffer(0))
            if not area.is_empty:
                yield feature(mapping(area))
        except (ValueError, TypeError, ezdxf.DXFError, GEOSException):
            warn("không đọc được vùng tô")
        return

    if entity_type in ("INSERT", "DIMENSION"):
        try:
            name = entity.dxf.name if entity_type == "INSERT" else "DIMENSION"
            if len(block_path) >= 20 or name in block_path:
                warn("block lặp hoặc quá nhiều cấp")
                return
            inserts = entity.multi_insert() if entity_type == "INSERT" and entity.mcount > 1 else [entity]
            for insert in inserts:
                for virtual_entity in insert.virtual_entities():
                    yield from _entity_features(virtual_entity, inherited_layer=layer,
                                                inherited_color=color, block_path=block_path + (name,),
                                                warnings=warnings)
        except (ValueError, TypeError, AttributeError, ezdxf.DXFError):
            warn("không đọc được block")
        return

    if entity_type not in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF"):
        warn("chưa hỗ trợ hiển thị")


def _read_text_lines(path):
    encodings = ("utf-8-sig", "utf-8", "cp1258", "cp1252", "latin-1")
    last_error = None
    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding) as file:
                return file.read().splitlines()
        except UnicodeDecodeError as exc:
            last_error = exc

    raise last_error or RuntimeError("Khong the doc noi dung DXF.")


def _repair_blank_group_codes(path):
    lines = _read_text_lines(path)
    repaired = []
    expecting_code = True

    for line in lines:
        if expecting_code and line.strip() == "":
            continue

        repaired.append(line)
        expecting_code = not expecting_code

    handle, repaired_path = tempfile.mkstemp(prefix="repaired_", suffix=".dxf")
    with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(repaired))
        file.write("\n")

    return repaired_path


def _read_dxf(path):
    try:
        return ezdxf.readfile(path)
    except Exception as first_error:
        try:
            doc, auditor = recover.readfile(path)
            return doc
        except Exception:
            repaired_path = _repair_blank_group_codes(path)
            try:
                try:
                    return ezdxf.readfile(repaired_path)
                except Exception:
                    doc, auditor = recover.readfile(repaired_path)
                    return doc
            except Exception:
                raise first_error
            finally:
                try:
                    os.remove(repaired_path)
                except OSError:
                    pass


def main():
    if len(sys.argv) < 2:
        _error("Usage: cad_to_geojson.py <input.dxf>")

    input_path = sys.argv[1]
    if not os.path.isfile(input_path):
        _error(f"Khong tim thay file DXF: {input_path}")

    if os.path.splitext(input_path)[1].lower() != ".dxf":
        _error("Fallback CAD reader chi ho tro file .dxf")

    try:
        with redirect_stdout(StringIO()):
            doc = _read_dxf(input_path)
            features = []
            for entity in doc.modelspace():
                features.extend(_entity_features(entity))

        print(json.dumps({
            "type": "FeatureCollection",
            "features": features,
        }, ensure_ascii=False))
    except Exception as exc:
        _error(str(exc))


if __name__ == "__main__":
    main()
