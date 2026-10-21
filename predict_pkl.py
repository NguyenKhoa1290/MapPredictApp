import sys
import json
import warnings
import joblib
import pandas as pd

FEATURES = [f"x{i}" for i in range(1, 10)]


def predict_rows(input_data, model_path, scaler_path):
    """Predict directly in Python, preserving the input columns and adding Y."""
    if not input_data:
        return []

    rows = []
    for row in input_data:
        values = {}
        for feature in FEATURES:
            try:
                values[feature] = float(row.get(feature, 0) or 0)
            except (ValueError, TypeError):
                values[feature] = 0.0
        rows.append(values)

    frame = pd.DataFrame(rows, columns=FEATURES)
    scaler = joblib.load(scaler_path)
    scaled = pd.DataFrame(scaler.transform(frame), columns=FEATURES)
    model = joblib.load(model_path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        labels = model.predict(scaled)

    if len(labels) != len(input_data):
        raise ValueError("Số kết quả dự đoán không khớp số dòng CSV.")
    return [{**row, "Y": int(label)} for row, label in zip(input_data, labels)]


def main():
    if len(sys.argv) < 4:
        print(json.dumps({"error": "Usage: predict_pkl.py <model.pkl> <scaler.pkl> <data.json>"}))
        sys.exit(1)

    model_path = sys.argv[1]
    scaler_path = sys.argv[2]
    data_path = sys.argv[3]

    # Load input data (ho tro ca UTF-8 va UTF-8 BOM)
    with open(data_path, 'r', encoding='utf-8-sig') as f:
        input_data = json.load(f)  # list of dicts

    predicted = predict_rows(input_data, model_path, scaler_path)
    print(json.dumps([row["Y"] for row in predicted]))

if __name__ == "__main__":
    main()
