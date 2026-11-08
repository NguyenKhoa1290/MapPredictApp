"""Environment settings shared by the AI worker and its web gateway."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]


class AIConfig:
    ASSISTANT_ENABLED = os.environ.get('MAP_PREDICT_ASSISTANT_ENABLED', '0') == '1'
    ASSISTANT_URL = os.environ.get('MAP_PREDICT_ASSISTANT_URL', 'http://127.0.0.1:8081/v1')
    ASSISTANT_MODEL = os.environ.get('MAP_PREDICT_ASSISTANT_MODEL', 'gemini-3.5-flash-lite')
    ASSISTANT_SECRET_FILE = os.environ.get('MAP_PREDICT_ASSISTANT_SECRET_FILE')
    ASSISTANT_RUBRIC = ROOT / 'ai_service' / 'prompts' / 'rubric.md'
    ASSISTANT_PROMPT = ROOT / 'ai_service' / 'prompts' / 'system_prompt.txt'
    ASSISTANT_SERVICE_URL = os.environ.get('MAP_PREDICT_AI_SERVICE_URL', '')
    ASSISTANT_ROLE = 'web'
    ASSISTANT_QDRANT_URL = os.environ.get('AI_QDRANT_URL', '')
    ASSISTANT_QDRANT_COLLECTION = os.environ.get('AI_QDRANT_COLLECTION', 'CSDL-Datdai')
    ASSISTANT_QDRANT_KEY = os.environ.get('AI_QDRANT_API_KEY', '')
    ASSISTANT_VECTOR_NAME = os.environ.get('AI_QDRANT_VECTOR_NAME', '')
    ASSISTANT_EMBEDDING_URL = os.environ.get('AI_EMBEDDING_URL', '')
    ASSISTANT_EMBEDDING_ENABLED = os.environ.get('AI_EMBEDDING_ENABLED', '0') == '1'
    ASSISTANT_EMBEDDING_MODEL = os.environ.get('AI_EMBEDDING_MODEL', 'qwen3-embedding:0.6b')
    AI_SETTINGS_FILE = os.environ.get('AI_SETTINGS_FILE')
    AI_ADMIN_PASSWORD_FILE = os.environ.get('AI_ADMIN_PASSWORD_FILE')
