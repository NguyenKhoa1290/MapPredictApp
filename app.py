"""Local Python web app for prediction and GeoPackage visualization."""

import csv
import io
import math
import os
import sqlite3
import tempfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.exceptions import HTTPException

from cad_diagnostics import cad_diagnostics
from gis import (cad_geojson, gpkg_columns, gpkg_diagnostics, parse_source_crs,
                 predicted_geojson, source_crs_options)
from predict_pkl import predict_rows


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "MapPredictApp"
RESULT_CSV = DATA_DIR / "KetQua.csv"
app = Flask(__name__, static_folder="wwwroot", static_url_path="/static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 600 * 1024 * 1024


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


def _write_results(rows):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with RESULT_CSV.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _saved_results():
    if not RESULT_CSV.is_file():
        return []
    return _csv_rows(RESULT_CSV.read_bytes())


def _model_source(field, default_name):
    uploaded = request.files.get(field)
    if uploaded and uploaded.filename:
        if Path(uploaded.filename).suffix.lower() != ".pkl":
            raise ValueError("Mô hình và bộ chuẩn hóa phải có định dạng .pkl.")
        try:
            return io.BytesIO(uploaded.read())
        finally:
            uploaded.close()
    default = ROOT / default_name
    if not default.is_file():
        raise ValueError(f"Không tìm thấy file mặc định {default_name}.")
    return default


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


@app.errorhandler(Exception)
def _api_error(error):
    if isinstance(error, HTTPException):
        return jsonify(error=str(error.description)), error.code
    if isinstance(error, (ValueError, OSError, sqlite3.Error)):
        return jsonify(error=str(error)), 400
    app.logger.exception("Unexpected application error")
    return jsonify(error="Không thể xử lý yêu cầu. Kiểm tra nhật ký ứng dụng."), 500


@app.get("/")
def home():
    asset_version = max((ROOT / "wwwroot" / filename).stat().st_mtime_ns
                        for filename in ("app.css", "app.js"))
    response = app.make_response(render_template(
        "index.html", asset_version=asset_version, crs_options=source_crs_options()))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/results")
def results():
    try:
        rows = _saved_results()
    except ValueError:
        rows = []
    return jsonify(rows=rows)


@app.post("/api/predict")
def predict():
    uploaded = request.files.get("csv")
    if not uploaded or not uploaded.filename:
        raise ValueError("Vui lòng chọn file CSV.")
    if Path(uploaded.filename).suffix.lower() != ".csv":
        raise ValueError("File dữ liệu phải có định dạng .csv.")
    try:
        rows = _csv_rows(uploaded.read())
    finally:
        uploaded.close()
    predicted = predict_rows(
        rows,
        _model_source("model", "rf_model_rating.pkl"),
        _model_source("scaler", "scaler_bds.pkl"),
    )
    _write_results(predicted)
    return jsonify(rows=predicted, saved_to=str(RESULT_CSV))


@app.post("/api/preview-csv")
def preview_csv():
    uploaded = request.files.get("csv")
    if not uploaded or not uploaded.filename or Path(uploaded.filename).suffix.lower() != ".csv":
        raise ValueError("Vui lòng chọn file dữ liệu CSV.")
    try:
        rows = _csv_rows(uploaded.read())
    finally:
        uploaded.close()
    return jsonify(rows=rows[:200], count=len(rows))


@app.get("/api/export")
def export():
    if not RESULT_CSV.is_file():
        raise ValueError("Chưa có kết quả để xuất.")
    return send_file(RESULT_CSV, mimetype="text/csv", as_attachment=True, download_name="KetQua.csv")


@app.post("/api/gpkg-columns")
def columns():
    with tempfile.TemporaryDirectory(prefix="map-predict-columns-") as directory:
        path = _uploaded_file("gpkg", {".gpkg"}, directory)
        if path is None:
            raise ValueError("Vui lòng chọn file GeoPackage.")
        diagnostics = gpkg_diagnostics(path)
        return jsonify(columns=gpkg_columns(path), crs=diagnostics["declared_crs"],
                       diagnostics=diagnostics)


@app.post("/api/result-columns")
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


@app.post("/api/cad-diagnostics")
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


@app.post("/api/map")
def map_layers():
    shared_crs = request.form.get("source_crs", "").strip().upper()
    if not shared_crs:
        raise ValueError("Vui lòng chọn hệ tọa độ chung (EPSG) ở thanh trên.")
    shared_crs = parse_source_crs(shared_crs).to_string()
    if any(file.filename for file in request.files.getlist("base")):
        raise ValueError("Layer nền dùng file DXF. GeoPackage chỉ dùng cho layer dự đoán.")
    with tempfile.TemporaryDirectory(prefix="map-predict-layers-") as directory:
        cad_layers = _uploaded_files("cad", {".dxf"}, directory)
        prediction_layers = _uploaded_files("layer", {".gpkg"}, directory)
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
            _write_results(rows)
        else:
            rows = _saved_results() if prediction_layers else []

        layers = []
        cad_x_values = request.form.getlist("cad_offset_x")
        cad_y_values = request.form.getlist("cad_offset_y")
        cad_ids = request.form.getlist("cad_id")
        prediction_ids = request.form.getlist("layer_id")
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
            if not rows:
                raise ValueError("Vui lòng chạy dự đoán hoặc chọn file kết quả CSV.")
            gpkg_join = request.form.get("gpkg_join", "")
            csv_join = request.form.get("csv_join", "")
            if not gpkg_join or not csv_join or csv_join not in rows[0]:
                raise ValueError("Vui lòng chọn hai cột ghép dữ liệu hợp lệ.")
            prediction_offset_x = _offset(request.form.get("prediction_offset_x"), "Dịch X layer dự đoán")
            prediction_offset_y = _offset(request.form.get("prediction_offset_y"), "Dịch Y layer dự đoán")
            declared_crs = gpkg_diagnostics(layer)["declared_crs"]
            layers.append({
                "kind": "prediction",
                "name": name,
                "source_id": prediction_ids[index] if index < len(prediction_ids) else f"prediction:{index}:{name}",
                "crs": shared_crs,
                "declared_crs": declared_crs,
                "offset_x": prediction_offset_x, "offset_y": prediction_offset_y,
                "data": predicted_geojson(layer, rows, gpkg_join, csv_join, shared_crs,
                                          prediction_offset_x, prediction_offset_y),
            })
        if not layers:
            raise ValueError("Vui lòng chọn ít nhất một file bản đồ.")
        counts = {str(label): sum(str(row.get("Y", "")) == str(label) for row in rows)
                  for label in (0, 1, 2)}
        return jsonify(layers=layers, source_crs=shared_crs, output_crs="EPSG:4326",
                       count=len(rows), counts=counts)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8765")), debug=False)
