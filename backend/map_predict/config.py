from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]


class Config:
    MAX_CONTENT_LENGTH = 600 * 1024 * 1024  # Existing local limit, not a public-deployment recommendation.
    FRONTEND_DIST = ROOT / "frontend" / "dist"
    PUBLIC_CONTENT_FILE = ROOT / "config" / "public_content.json"
    PROJECT_CATALOG_FILE = ROOT / "config" / "projects.json"
    PROJECT_SOURCE_FOLDER = ROOT / "Tailieuthamkhao" / "Giaodienfrontend" / "luoi"
    MODEL_DIRECTORY = Path(os.environ.get("MAP_PREDICT_MODEL_DIR", ROOT / "models"))
    MODEL_RELEASE = os.environ.get("MAP_PREDICT_MODEL_RELEASE", "pipeline-v1")
    PREDICTION_MAX_CSV_BYTES = 5 * 1024 * 1024
    PREDICTION_MAX_REQUEST_BYTES = 8 * 1024 * 1024
    PREDICTION_MAX_ROWS = 10000
