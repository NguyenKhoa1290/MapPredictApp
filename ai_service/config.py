"""Configuration for the independently deployed AI worker."""
from shared.ai_config import AIConfig


class Config(AIConfig):
    ASSISTANT_ENABLED = True
    ASSISTANT_ROLE = "worker"
    ASSISTANT_SERVICE_URL = ""
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    PREDICTION_MAX_ROWS = 10000
