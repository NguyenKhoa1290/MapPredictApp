"""Local Python web app for prediction and GeoPackage visualization."""

import csv
import io
import math
import os
import sqlite3
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, redirect, render_template, request
from werkzeug.exceptions import HTTPException

from cad_diagnostics import cad_diagnostics
from gis import (cad_geojson, gpkg_columns, gpkg_diagnostics, parse_source_crs,
                 predicted_geojson, source_crs_options)
from backend.map_predict.services.prediction import PredictionError, run_prediction
from prediction_grid import dxf_grid_metadata, predicted_dxf_grid
from backend.map_predict import create_app


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "MapPredictApp"
RESULT_CSV = DATA_DIR / "KetQua.csv"
legacy = Blueprint("legacy", __name__)


@legacy.before_request
def legacy_same_origin():
    if request.method == "POST" and request.headers.get("Origin"):
        origin, host = urlsplit(request.headers["Origin"]), urlsplit(request.host_url)
        if (origin.scheme, origin.netloc) != (host.scheme, host.netloc):
            return jsonify(error="Yêu cầu phải gửi từ cùng website"), 403


def _csv_rows(data):
    for encoding in ("utf-8-sig", "cp1258", "cp1252"):
        try:
            content = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Không thể đọc mã hóa của file CSV.")
    reader = csv.DictReader(io.StringIO(content, newline=""))
    if not reader.fieldnames:
        raise ValueError("File CSV thiếu hàng tiêu đề.")
    rows = list(reader)
    if not rows:
        raise ValueError("File CSV không có dữ liệu.")
    if any(None in row for row in rows):
        raise ValueError("Một số dòng CSV có nhiều cột hơn hàng tiêu đề.")
    return rows


def _uploaded_file(name, suffix, directory):
    uploaded = request.files.get(name)
    if not uploaded or not uploaded.filename:
        return None
    if Path(uploaded.filename).suffix.lower() not in suffix:
        raise ValueError(f"Định dạng file {name} không hợp lệ.")
    path = Path(directory) / (name + Path(uploaded.filename).suffix.lower())
    try:
        uploaded.save(path)
    finally:
        uploaded.close()
    return path


def _uploaded_files(name, suffix, directory):
    paths = []
    for index, uploaded in enumerate(request.files.getlist(name)):
        if not uploaded or not uploaded.filename:
            continue
        if Path(uploaded.filename).suffix.lower() not in suffix:
            raise ValueError(f"Định dạng file {name} không hợp lệ.")
        path = Path(directory) / f"{name}-{index}{Path(uploaded.filename).suffix.lower()}"
        try:
            uploaded.save(path)
        finally:
            uploaded.close()
        paths.append((path, Path(uploaded.filename).name))
    return paths


def _offset(value, label):
    try:
        number = float(value or 0)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} phải là số (mét).") from error
    if not math.isfinite(number):
        raise ValueError(f"{label} phải là số hữu hạn (mét).")
    return number


def _api_error(error):
    if isinstance(error, HTTPException):
        return jsonify(error=str(error.description)), error.code
    if isinstance(error, (ValueError, OSError, sqlite3.Error)):
        return jsonify(error=str(error)), 400
    current_app.logger.exception("Unexpected application error")
    return jsonify(error="Không thể xử lý yêu cầu. Kiểm tra nhật ký ứng dụng."), 500


@legacy.get("/")
@legacy.get("/legacy/")
def home():
    if request.path == '/':
        return redirect('/portal/')
    if request.args.get('embedded') != '1':
        return redirect('/portal/assessment')
    asset_version = max((ROOT / "wwwroot" / filename).stat().st_mtime_ns
                        for filename in ("app.css", "app.js", "basemaps.js", "color_adjustments.js", "layer_manager.js",
                                         "workspace_store.js", "workspace.js", "pdf_export.js", "join_preview.js"))
    response = current_app.make_response(render_template(
        "index.html", asset_version=asset_version, crs_options=source_crs_options()))
    response.headers["Cache-Control"] = "no-store"
    return response


@legacy.get("/api/results")
def results():
    return jsonify(rows=[])


@legacy.post("/api/predict")
def predict():
    request.max_content_length = current_app.config["PREDICTION_MAX_REQUEST_BYTES"]
    if set(request.files) - {"csv"} or request.form:
        return jsonify(error="Chỉ nhận CSV, mô hình được quản lý trên máy chủ"), 400
    uploaded = request.files.get("csv")
    if not uploaded or not uploaded.filename:
        raise ValueError("Vui lòng chọn file CSV.")
    if Path(uploaded.filename).suffix.lower() != ".csv":
        raise ValueError("File dữ liệu phải có định dạng .csv.")
    try:
        content = uploaded.read(current_app.config["PREDICTION_MAX_CSV_BYTES"] + 1)
        if len(content) > current_app.config["PREDICTION_MAX_CSV_BYTES"]:
            return jsonify(error="CSV vượt giới hạn dung lượng cho phép"), 413
        rows = _csv_rows(content)
        result = run_prediction(rows, current_app.config)
    except PredictionError as error:
        return jsonify(error=str(error)), error.status
    finally:
        uploaded.close()
    predicted = result["rows"]
    return jsonify(rows=predicted, model_version=result["model_version"])


@legacy.post("/api/preview-csv")
def preview_csv():
    uploaded = request.files.get("csv")
    if not uploaded or not uploaded.filename or Path(uploaded.filename).suffix.lower() != ".csv":
        raise ValueError("Vui lòng chọn file dữ liệu CSV.")
    try:
        rows = _csv_rows(uploaded.read())
    finally:
        uploaded.close()
    return jsonify(rows=rows[:200], count=len(rows))


@legacy.get("/api/export")
def export():
    return jsonify(error="Xuất CSV từ bảng kết quả trong phiên đang mở"), 410


@legacy.post("/api/gpkg-columns")
def columns():
    with tempfile.TemporaryDirectory(prefix="map-predict-columns-") as directory:
        path = _uploaded_file("gpkg", {".gpkg"}, directory)
        if path is None:
            raise ValueError("Vui lòng chọn file GeoPackage.")
        diagnostics = gpkg_diagnostics(path)
        return jsonify(columns=gpkg_columns(path), crs=diagnostics["declared_crs"],
                       diagnostics=diagnostics)


@legacy.post("/api/result-columns")
def result_columns():
    uploaded = request.files.get("result")
    if not uploaded or not uploaded.filename or Path(uploaded.filename).suffix.lower() != ".csv":
        raise ValueError("Vui lòng chọn file kết quả CSV.")
    try:
        rows = _csv_rows(uploaded.read())
    finally:
        uploaded.close()
    if "Y" not in rows[0]:
        raise ValueError("File kết quả phải có cột Y.")
    return jsonify(columns=[name for name in rows[0] if name != "Y"], count=len(rows))


@legacy.post("/api/prediction-columns")
def prediction_columns():
    with tempfile.TemporaryDirectory(prefix="map-predict-grid-columns-") as directory:
        path = _uploaded_file("layer", {".gpkg", ".dxf"}, directory)
        if path is None:
            raise ValueError("Vui lòng chọn lưới dự đoán DXF hoặc GeoPackage.")
        if path.suffix.lower() == ".dxf":
            metadata = dxf_grid_metadata(path)
            return jsonify(columns=metadata["columns"], crs=None, format="dxf",
                           suggested_join=metadata["suggested_join"], diagnostics=metadata)
        diagnostics = gpkg_diagnostics(path)
        return jsonify(columns=gpkg_columns(path), crs=diagnostics["declared_crs"],
                       format="gpkg", diagnostics=diagnostics)


@legacy.post("/api/cad-diagnostics")
def diagnose_cad():
    source_crs = request.form.get("source_crs", "").strip().upper()
    if not source_crs:
        raise ValueError("Vui lòng chọn hệ tọa độ chung (EPSG) trước khi phân tích.")
    parse_source_crs(source_crs)
    with tempfile.TemporaryDirectory(prefix="map-predict-cad-diagnosis-") as directory:
        path = _uploaded_file("cad", {".dxf"}, directory)
        if path is None:
            raise ValueError("Vui lòng chọn file DXF để phân tích.")
        return jsonify(cad_diagnostics(path, source_crs))


@legacy.post("/api/map")
def map_layers():
    join_mode = request.form.get("join_mode", "exact")
    if join_mode not in ("exact", "numeric"):
        raise ValueError("Chế độ ghép phải là exact hoặc numeric")
    shared_crs = request.form.get("source_crs", "").strip().upper()
    if not shared_crs:
        raise ValueError("Vui lòng chọn hệ tọa độ chung (EPSG) ở thanh trên.")
    shared_crs = parse_source_crs(shared_crs).to_string()
    if any(file.filename for file in request.files.getlist("base")):
        raise ValueError("Layer nền dùng file DXF. GeoPackage chỉ dùng cho layer dự đoán.")
    with tempfile.TemporaryDirectory(prefix="map-predict-layers-") as directory:
        cad_layers = _uploaded_files("cad", {".dxf"}, directory)
        prediction_layers = _uploaded_files("layer", {".gpkg", ".dxf"}, directory)
        result = request.files.get("result")

        if result and result.filename:
            if Path(result.filename).suffix.lower() != ".csv":
                raise ValueError("File kết quả phải có định dạng .csv.")
            try:
                rows = _csv_rows(result.read())
            finally:
                result.close()
            if "Y" not in rows[0]:
                raise ValueError("File kết quả phải có cột Y.")
        else:
            rows = []

        layers = []
        cad_x_values = request.form.getlist("cad_offset_x")
        cad_y_values = request.form.getlist("cad_offset_y")
        cad_ids = request.form.getlist("cad_id")
        prediction_ids = request.form.getlist("layer_id")
        prediction_joins = request.form.getlist("layer_join")
        for index, (cad, name) in enumerate(cad_layers):
            offset_x = _offset(cad_x_values[index] if index < len(cad_x_values) else 0,
                               f"Dịch X {name}")
            offset_y = _offset(cad_y_values[index] if index < len(cad_y_values) else 0,
                               f"Dịch Y {name}")
            layers.append({"kind": "base", "name": name,
                           "source_id": cad_ids[index] if index < len(cad_ids) else f"cad:{index}:{name}",
                           "crs": shared_crs,
                           "offset_x": offset_x, "offset_y": offset_y,
                           "data": cad_geojson(cad, shared_crs, offset_x, offset_y)})
        for index, (layer, name) in enumerate(prediction_layers):
            is_dxf = layer.suffix.lower() == ".dxf"
            gpkg_join = (prediction_joins[index] if index < len(prediction_joins)
                         else request.form.get("gpkg_join", ""))
            csv_join = request.form.get("csv_join", "")
            if rows and (not gpkg_join or not csv_join or csv_join not in rows[0]):
                raise ValueError("Vui lòng chọn hai cột ghép dữ liệu hợp lệ.")
            prediction_offset_x = _offset(request.form.get("prediction_offset_x"), "Dịch X layer dự đoán")
            prediction_offset_y = _offset(request.form.get("prediction_offset_y"), "Dịch Y layer dự đoán")
            declared_crs = None if is_dxf else gpkg_diagnostics(layer)["declared_crs"]
            data = (predicted_dxf_grid(layer, rows, gpkg_join, csv_join, shared_crs,
                                       prediction_offset_x, prediction_offset_y, join_mode) if is_dxf else
                    predicted_geojson(layer, rows, gpkg_join, csv_join, shared_crs,
                                      prediction_offset_x, prediction_offset_y, join_mode))
            layers.append({
                "kind": "prediction",
                "name": name,
                "source_id": prediction_ids[index] if index < len(prediction_ids) else f"prediction:{index}:{name}",
                "crs": shared_crs,
                "declared_crs": declared_crs,
                "format": "dxf" if is_dxf else "gpkg",
                "offset_x": prediction_offset_x, "offset_y": prediction_offset_y,
                "data": data,
            })
        if not layers:
            raise ValueError("Vui lòng chọn ít nhất một file bản đồ.")
        counts = {str(label): sum(str(row.get("Y", "")) == str(label) for row in rows)
                  for label in (0, 1, 2)}
        return jsonify(layers=layers, source_crs=shared_crs, output_crs="EPSG:4326",
                       count=len(rows), counts=counts)


app = create_app(legacy_blueprint=legacy, legacy_error_handler=_api_error)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8765")), debug=False)
