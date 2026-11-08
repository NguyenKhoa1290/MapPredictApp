"""Shared CSV parsing and structured validation errors."""
import csv
import io

class PredictionError(ValueError):
    def __init__(self, code, message, status=422):
        super().__init__(message)
        self.code, self.status = code, status


def read_csv(data, max_rows, *, allow_empty=False, with_columns=False):
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
    if not rows and not allow_empty:
        raise PredictionError("EMPTY_CSV", "CSV chưa có dòng dữ liệu")
    return (rows, names) if with_columns else rows
