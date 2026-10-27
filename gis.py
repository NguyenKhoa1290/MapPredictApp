"""GeoPackage and CAD conversion for the Python web application."""

import sqlite3
import tempfile
import math
import re
import struct
from contextlib import closing
from pathlib import Path

from pyproj import CRS, Transformer
from pyproj.exceptions import ProjError
from shapely import wkb
from shapely.affinity import translate
from shapely.geometry import mapping, shape
from shapely.ops import transform

from cad_to_geojson import _entity_features, _read_dxf
from dwg_to_dxf import ODA_DOWNLOAD_URL, _configure_oda_path, _find_oda_converter


def _identifier(name):
    return '"' + name.replace('"', '""') + '"'


def _layers(connection):
    return connection.execute(
        "SELECT table_name, column_name, geometry_type_name, srs_id "
        "FROM gpkg_geometry_columns"
    ).fetchall()


def _columns(connection, table):
    return [row[1] for row in connection.execute(f"PRAGMA table_info({_identifier(table)})")]


def gpkg_columns(path):
    with closing(sqlite3.connect(path)) as connection:
        layers = _layers(connection)
        if not layers:
            raise ValueError("GeoPackage không có lớp dữ liệu hình học.")
        available = [[column for column in _columns(connection, table) if column != geometry_column]
                     for table, geometry_column, _, _ in layers]
        return [column for column in available[0] if all(column in columns for columns in available)]


VN2000_EPSG_CODES = (
    3405, 3406, 5896, 5897, 5898, 5899,
    *range(9205, 9219),
)


def parse_source_crs(value):
    if not re.fullmatch(r"EPSG:\d{4,6}", value, flags=re.IGNORECASE):
        raise ValueError("Hệ tọa độ chung phải có dạng EPSG:5897.")
    try:
        return CRS.from_epsg(int(value.split(":", 1)[1]))
    except (ValueError, TypeError, ProjError) as error:
        raise ValueError(f"Không tìm thấy hệ tọa độ {value}.") from error


def source_crs_options():
    return [{"code": f"EPSG:{code}", "name": CRS.from_epsg(code).name}
            for code in (*VN2000_EPSG_CODES, 4326)]


def _source_crs(connection, srs_id, override=None):
    if override:
        return parse_source_crs(override)
    row = connection.execute(
        "SELECT organization, organization_coordsys_id, definition "
        "FROM gpkg_spatial_ref_sys WHERE srs_id = ?", (srs_id,)
    ).fetchone()
    if row is None or srs_id in (0, -1):
        raise ValueError("Layer GeoPackage không khai báo hệ tọa độ hợp lệ.")
    organization, code, definition = row
    try:
        if organization and organization.upper() == "EPSG" and code:
            return CRS.from_epsg(int(code))
        return CRS.from_wkt(definition)
    except (ValueError, TypeError, ProjError) as error:
        raise ValueError(f"Không đọc được hệ tọa độ GeoPackage (srs_id={srs_id}).") from error


def gpkg_crs(path):
    with closing(sqlite3.connect(path)) as connection:
        layers = _layers(connection)
        if not layers:
            raise ValueError("GeoPackage không có lớp dữ liệu hình học.")
        crs = _source_crs(connection, layers[0][3])
        return crs.to_string()


def gpkg_diagnostics(path, offset_x=0, offset_y=0):
    """Report metadata and alternative placements; coordinates alone cannot prove a CRS."""
    with closing(sqlite3.connect(path)) as connection:
        layers = _layers(connection)
        if not layers:
            raise ValueError("GeoPackage không có lớp dữ liệu hình học.")
        table, geometry_column, _, srs_id = layers[0]
        first_geometry = connection.execute(
            f"SELECT {_identifier(geometry_column)} FROM {_identifier(table)} "
            f"WHERE {_identifier(geometry_column)} IS NOT NULL LIMIT 1"
        ).fetchone()
        geometry_srs_id = None
        if first_geometry and first_geometry[0] and len(first_geometry[0]) >= 8 and first_geometry[0][:2] == b"GP":
            blob = first_geometry[0]
            geometry_srs_id = struct.unpack("<i" if blob[3] & 1 else ">i", blob[4:8])[0]
        try:
            declared = _source_crs(connection, srs_id).to_string()
        except ValueError:
            declared = None
        bounds = connection.execute(
            "SELECT min_x, min_y, max_x, max_y FROM gpkg_contents WHERE table_name = ?",
            (table,),
        ).fetchone()
        if not bounds or any(value is None for value in bounds):
            bounds = None
            query = (f"SELECT {_identifier(geometry_column)} FROM {_identifier(table)} "
                     "WHERE " + _identifier(geometry_column) + " IS NOT NULL LIMIT 200")
            for (blob,) in connection.execute(query):
                geometry = _geometry(blob)
                if geometry is None:
                    continue
                current = shape(geometry).bounds
                if bounds is None:
                    bounds = current
                else:
                    bounds = (min(bounds[0], current[0]), min(bounds[1], current[1]),
                              max(bounds[2], current[2]), max(bounds[3], current[3]))
        if bounds is None:
            return {"declared_crs": declared, "geometry_srs_id": geometry_srs_id,
                    "raw_bounds": None, "candidates": []}

        center_x = (bounds[0] + bounds[2]) / 2 + offset_x
        center_y = (bounds[1] + bounds[3]) / 2 + offset_y
        codes = set(VN2000_EPSG_CODES)
        if declared and declared.startswith("EPSG:"):
            codes.add(int(declared.split(":", 1)[1]))
        if -180 <= center_x <= 180 and -90 <= center_y <= 90:
            codes.update((4326, 4756))
        candidates = []
        for code in codes:
            try:
                crs = CRS.from_epsg(code)
                longitude, latitude = _transformer(crs).transform(center_x, center_y)
                if not (math.isfinite(longitude) and math.isfinite(latitude)):
                    continue
                area = crs.area_of_use
                in_area = bool(area and area.west <= longitude <= area.east
                               and area.south <= latitude <= area.north)
                candidates.append({
                    "crs": f"EPSG:{code}", "name": crs.name,
                    "longitude": round(longitude, 6), "latitude": round(latitude, 6),
                    "in_area": in_area, "declared": f"EPSG:{code}" == declared,
                })
            except (ValueError, TypeError, ProjError):
                continue
        candidates.sort(key=lambda item: (not item["declared"], not item["in_area"], item["crs"]))
        return {"declared_crs": declared, "geometry_srs_id": geometry_srs_id,
                "raw_bounds": list(bounds), "offset_x": offset_x, "offset_y": offset_y,
                "candidates": candidates}


def _to_wgs84(geometry, transformer, offset_x=0, offset_y=0):
    source = shape(geometry)
    if offset_x or offset_y:
        source = translate(source, xoff=offset_x, yoff=offset_y)
    projected = transform(transformer.transform, source)
    if projected.is_empty:
        return None
    west, south, east, north = projected.bounds
    if not all(-180 <= value <= 180 for value in (west, east)) or not all(
        -90 <= value <= 90 for value in (south, north)
    ):
        raise ValueError("Tọa độ nằm ngoài phạm vi kinh/vĩ độ. Hãy kiểm tra EPSG nguồn của layer.")
    return mapping(projected)


def _transformer(source_crs):
    try:
        return Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
    except (ValueError, TypeError, ProjError) as error:
        raise ValueError("EPSG nguồn không hợp lệ.") from error


def _geometry(blob):
    if not blob or len(blob) < 8 or blob[:2] != b"GP":
        return None
    envelope = (blob[3] >> 1) & 7
    header_length = {0: 8, 1: 40, 2: 56, 3: 56, 4: 72}.get(envelope)
    if header_length is None or len(blob) <= header_length:
        return None
    return mapping(wkb.loads(blob[header_length:]))


def _is_text_feature(table, properties, geometry):
    if geometry["type"] not in ("Point", "MultiPoint"):
        return False
    if any(str(properties.get(name) or "").strip() for name in ("text", "label", "mtext")):
        return True
    return any(word in table.lower() for word in ("text", "label", "annotation"))


def base_geojson(path, source_crs=None, offset_x=0, offset_y=0):
    features = []
    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        for table, geometry_column, _, srs_id in _layers(connection):
            transformer = _transformer(_source_crs(connection, srs_id, source_crs))
            columns = [name for name in _columns(connection, table) if name != geometry_column]
            selected = ", ".join(_identifier(name) for name in columns)
            query = f"SELECT {_identifier(geometry_column)} AS geometry_blob"
            if selected:
                query += f", {selected}"
            query += f" FROM {_identifier(table)}"
            for row in connection.execute(query):
                try:
                    geometry = _geometry(row["geometry_blob"])
                    if geometry is None:
                        continue
                    properties = {name: row[name] for name in columns if row[name] is not None}
                    if _is_text_feature(table, properties, geometry):
                        continue
                except (ValueError, IndexError, TypeError):
                    continue
                geometry = _to_wgs84(geometry, transformer, offset_x, offset_y)
                features.append({"type": "Feature", "geometry": geometry, "properties": properties})
    return {"type": "FeatureCollection", "features": features}


def predicted_geojson(path, rows, gpkg_join, csv_join, source_crs=None,
                      offset_x=0, offset_y=0, join_mode="exact"):
    from result_join import apply_results
    with closing(sqlite3.connect(path)) as connection:
        layers = _layers(connection)
        if not layers:
            raise ValueError("GeoPackage không có lớp dữ liệu hình học.")
        features = []
        for table, geometry_column, _, srs_id in layers:
            transformer = _transformer(_source_crs(connection, srs_id, source_crs))
            columns = [name for name in _columns(connection, table) if name != geometry_column]
            if gpkg_join not in columns:
                raise ValueError(f"Không tìm thấy cột {gpkg_join} trong bảng {table} của GeoPackage.")
            query = (f"SELECT {_identifier(geometry_column)}, "
                     + ", ".join(_identifier(name) for name in columns)
                     + f" FROM {_identifier(table)}")
            for blob, *values in connection.execute(query):
                try:
                    geometry = _geometry(blob)
                    if geometry is None:
                        continue
                    properties = {name: (value.hex() if isinstance(value, bytes) else value)
                                  for name, value in zip(columns, values)}
                except (ValueError, IndexError, TypeError):
                    continue
                geometry = _to_wgs84(geometry, transformer, offset_x, offset_y)
                features.append({
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        **properties,
                        "source_table": table,
                    },
                })
    return apply_results({"type": "FeatureCollection", "features": features},
                         rows, gpkg_join, csv_join, join_mode)


def cad_geojson(path, source_crs, offset_x=0, offset_y=0):
    path = Path(path)
    if path.suffix.lower() not in (".dxf", ".dwg"):
        raise ValueError("File CAD phải có định dạng .dxf hoặc .dwg.")

    dxf_path = path
    if path.suffix.lower() == ".dwg":
        from ezdxf.addons import odafc

        executable = _find_oda_converter()
        if executable:
            _configure_oda_path(executable)
        if not odafc.is_installed():
            raise ValueError(f"Cần cài ODA File Converter để đọc DWG: {ODA_DOWNLOAD_URL}")

        with tempfile.TemporaryDirectory(prefix="map-predict-cad-") as temp_dir:
            dxf_path = Path(temp_dir) / "converted.dxf"
            odafc.convert(str(path), str(dxf_path), version="R2010", audit=False, replace=True)
            return cad_geojson(dxf_path, source_crs, offset_x, offset_y)

    if not source_crs:
        raise ValueError("File CAD không chứa hệ tọa độ. Vui lòng nhập EPSG nguồn.")
    transformer = _transformer(source_crs)
    document = _read_dxf(str(dxf_path))
    features = []
    warnings = {}
    for entity in document.modelspace():
        for feature in _entity_features(entity, warnings=warnings):
            if feature.get("geometry"):
                feature["geometry"] = _to_wgs84(feature["geometry"], transformer,
                                                 offset_x, offset_y)
                features.append(feature)
    return {"type": "FeatureCollection", "features": features, "warnings": warnings}
