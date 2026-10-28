from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]


class Config:
    MAX_CONTENT_LENGTH = int(os.environ.get("MAP_PREDICT_MAX_UPLOAD_BYTES", 600 * 1024 * 1024))
    PROXY_HOPS = int(os.environ.get("MAP_PREDICT_PROXY_HOPS", "0"))
    FRONTEND_DIST = ROOT / "frontend" / "dist"
    PUBLIC_CONTENT_FILE = ROOT / "config" / "public_content.json"
    PROJECT_CATALOG_FILE = ROOT / "config" / "projects.json"
    PROJECT_SOURCE_FOLDER = Path(os.environ.get("MAP_PREDICT_PROJECT_SOURCE_FOLDER",
                                              ROOT / "Tailieuthamkhao" / "Giaodienfrontend" / "luoi"))
    MODEL_DIRECTORY = Path(os.environ.get("MAP_PREDICT_MODEL_DIR", ROOT / "models"))
    MODEL_RELEASE = os.environ.get("MAP_PREDICT_MODEL_RELEASE", "pipeline-v1")
    PREDICTION_MAX_CSV_BYTES = 5 * 1024 * 1024
    PREDICTION_MAX_REQUEST_BYTES = 8 * 1024 * 1024
    PREDICTION_MAX_ROWS = 10000
    ASSISTANT_ENABLED = os.environ.get('MAP_PREDICT_ASSISTANT_ENABLED', '0') == '1'
    ASSISTANT_URL = os.environ.get('MAP_PREDICT_ASSISTANT_URL', 'http://127.0.0.1:8081/v1')
    ASSISTANT_MODEL = os.environ.get('MAP_PREDICT_ASSISTANT_MODEL', 'gemini-3.6-flash')
    ASSISTANT_SECRET_FILE = os.environ.get('MAP_PREDICT_ASSISTANT_SECRET_FILE')
    ASSISTANT_RUBRIC = ROOT / 'config' / 'assistant' / 'rubric.md'
    ASSISTANT_PROMPT = ROOT / 'config' / 'assistant' / 'system_prompt.txt'
    ASSISTANT_SERVICE_URL = os.environ.get('MAP_PREDICT_AI_SERVICE_URL', '')
    ASSISTANT_ROLE = 'web'
    ASSISTANT_QDRANT_URL = os.environ.get('AI_QDRANT_URL', '')
    ASSISTANT_QDRANT_COLLECTION = os.environ.get('AI_QDRANT_COLLECTION', 'CSDL-Datdai')
    ASSISTANT_QDRANT_KEY = os.environ.get('AI_QDRANT_API_KEY', '')
    ASSISTANT_VECTOR_NAME = os.environ.get('AI_QDRANT_VECTOR_NAME', '')
    ASSISTANT_EMBEDDING_URL = os.environ.get('AI_EMBEDDING_URL', '')
    ASSISTANT_EMBEDDING_MODEL = os.environ.get('AI_EMBEDDING_MODEL', 'qwen3-embedding:0.6b')
