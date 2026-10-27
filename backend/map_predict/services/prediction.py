"""Predictions using the operator's fixed model bundle, with no result-file writes."""
import csv
import hashlib
import io
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path

from predict_pkl import FEATURES, predict_rows


class PredictionError(ValueError):
    def __init__(self, code, message, status=422):
        super().__init__(message)
        self.code, self.status = code, status


def bundle(config):
    directory = Path(config["MODEL_DIRECTORY"])
    try:
        model = (directory / "rf_model_rating_pipeline.pkl").read_bytes()
    except OSError as error:
        raise PredictionError("MODEL_UNAVAILABLE", "Mô hình trên máy chủ chưa sẵn sàng", 503) from error
    if not model:
        raise PredictionError("MODEL_UNAVAILABLE", "Bộ mô hình trên máy chủ chưa đầy đủ", 503)
    digest = hashlib.sha256(model).hexdigest()
    return model, f"{config['MODEL_RELEASE']}-{digest[:16]}"


def model_status(config):
    try:
        _, version = bundle(config)
        return {"ready": True, "model_version": version, "features": FEATURES,
                "message": "Đã có mô hình pipeline trên máy chủ"}
    except PredictionError as error:
        return {"ready": False, "model_version": None, "features": FEATURES, "message": str(error)}


def read_csv(data, max_rows):
    for encoding in ("utf-8-sig", "cp1258", "cp1252"):
        try:
            content = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise PredictionError("INVALID_CSV", "Không đọc được mã hóa CSV")
    try:
        reader = csv.DictReader(io.StringIO(content, newline=""))
        names = reader.fieldnames
        if not names or any(not name.strip() for name in names) or len(set(names)) != len(names):
            raise PredictionError("INVALID_CSV", "CSV cần hàng tiêu đề với tên cột rõ ràng và không trùng")
        rows = []
        for row in reader:
            if None in row:
                raise PredictionError("INVALID_CSV", "Số cột dữ liệu vượt quá hàng tiêu đề")
            if len(rows) >= max_rows:
                raise PredictionError("TOO_MANY_ROWS", f"Mỗi lần dự đoán hỗ trợ tối đa {max_rows} dòng", 413)
            rows.append({name: value if value is not None else "" for name, value in row.items()})
    except (csv.Error, UnicodeError) as error:
        raise PredictionError("INVALID_CSV", "Không đọc được cấu trúc CSV") from error
    if not rows:
        raise PredictionError("EMPTY_CSV", "CSV chưa có dòng dữ liệu")
    return rows


def run_prediction(rows, config):
    if not rows:
        raise PredictionError("EMPTY_CSV", "CSV chưa có dòng dữ liệu")
    if len(rows) > config["PREDICTION_MAX_ROWS"]:
        raise PredictionError("TOO_MANY_ROWS", "Số dòng vượt giới hạn dự đoán", 413)
    for index, row in enumerate(rows, 2):
        for feature in FEATURES:
            try:
                value = float(row.get(feature, 0) or 0)
            except (TypeError, ValueError) as error:
                raise PredictionError("INVALID_INPUT", f"Giá trị {feature} ở dòng {index} phải là số") from error
            if not math.isfinite(value):
                raise PredictionError("INVALID_INPUT", f"Giá trị {feature} ở dòng {index} phải là số hữu hạn")
    model, version = bundle(config)
    try:
        # The pipeline handles preprocessing itself, using one operator-owned file.
        predicted = predict_rows(rows, io.BytesIO(model))
    except Exception as error:
        raise PredictionError("MODEL_INCOMPATIBLE", "Bộ mô hình chưa tương thích với dữ liệu đầu vào", 503) from error
    if len(predicted) != len(rows) or any(row.get("Y") not in (0, 1, 2) for row in predicted):
        raise PredictionError("MODEL_INCOMPATIBLE", "Mô hình trả kết quả ngoài các nhãn Y được hỗ trợ", 503)
    return {"rows": predicted, "count": len(predicted), "columns": list(predicted[0]), "model_version": version}


def imported_results(rows):
    if not rows or 'Y' not in rows[0]:
        raise PredictionError('RESULT_Y_REQUIRED', 'CSV kết quả cần có cột Y')
    output = []
    for index, row in enumerate(rows, 2):
        raw = row.get('Y', '')
        if raw is None or not str(raw).strip():
            value = ''
        else:
            try:
                number = Decimal(str(raw).strip())
            except InvalidOperation as error:
                raise PredictionError('INVALID_RESULT_Y', f'Nhãn Y ở dòng {index} phải là 0, 1 hoặc 2') from error
            if not number.is_finite() or number not in (0, 1, 2):
                raise PredictionError('INVALID_RESULT_Y', f'Nhãn Y ở dòng {index} phải là 0, 1 hoặc 2')
            value = int(number)
        output.append({**row, 'Y': value})
    return {'rows': output, 'columns': list(output[0]), 'count': len(output), 'model_version': None, 'source': 'uploaded'}
