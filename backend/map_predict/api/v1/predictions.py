from pathlib import Path
from urllib.parse import urlsplit

from flask import Blueprint, current_app, g, jsonify, request

from ...services.prediction import PredictionError, imported_results, model_status, read_csv, run_prediction

predictions = Blueprint("predictions_v1", __name__, url_prefix="/api/v1/predictions")


@predictions.after_request
def private_response(result):
    result.headers["Cache-Control"] = "no-store"
    return result


@predictions.before_request
def prediction_limits():
    request.max_content_length = current_app.config["PREDICTION_MAX_REQUEST_BYTES"]
    if request.method == "POST" and request.headers.get("Origin"):
        origin = urlsplit(request.headers["Origin"])
        host = urlsplit(request.host_url)
        if (origin.scheme, origin.netloc) != (host.scheme, host.netloc):
            raise PredictionError("ORIGIN_NOT_ALLOWED", "Yêu cầu dự đoán phải gửi từ cùng website", 403)


@predictions.errorhandler(PredictionError)
def prediction_error(error):
    if error.status >= 500:
        current_app.logger.warning("Prediction request failed: %s", error.code, exc_info=True)
    return jsonify(error={"code": error.code, "message": str(error)}, request_id=g.request_id), error.status


def response(data):
    result = jsonify(data=data, meta={"schema": 1, "request_id": g.request_id})
    result.headers["Cache-Control"] = "no-store"
    return result


def uploaded_rows():
    if set(request.files) - {"csv"} or request.form:
        raise PredictionError("MODEL_UPLOAD_DISABLED", "Chỉ nhận CSV, mô hình được quản lý trên máy chủ", 400)
    sources = request.files.getlist("csv")
    if len(sources) != 1 or not sources[0].filename or Path(sources[0].filename).suffix.lower() != ".csv":
        raise PredictionError("CSV_REQUIRED", "Chọn một file CSV để tiếp tục", 400)
    source = sources[0]
    try:
        content = source.read(current_app.config["PREDICTION_MAX_CSV_BYTES"] + 1)
    finally:
        source.close()
    if len(content) > current_app.config["PREDICTION_MAX_CSV_BYTES"]:
        raise PredictionError("CSV_TOO_LARGE", "CSV vượt giới hạn dung lượng cho phép", 413)
    return read_csv(content, current_app.config["PREDICTION_MAX_ROWS"])


@predictions.get("/model")
def status():
    return response(model_status(current_app.config))


@predictions.post("/preview")
def preview():
    rows = uploaded_rows()
    return response({"rows": rows, "count": len(rows), "columns": list(rows[0])})


@predictions.post("")
def predict():
    return response(run_prediction(uploaded_rows(), current_app.config))


@predictions.post('/results')
def import_results():
    return response(imported_results(uploaded_rows()))
