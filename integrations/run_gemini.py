"""Run the supplied Gemini adapter on the private Compose network."""
from pathlib import Path
from gemini_web2api.config import CONFIG
from gemini_web2api.server import GeminiHandler, ThreadedServer

token = Path('/run/secrets/assistant_key').read_text().strip()
CONFIG.update(host='0.0.0.0', port=8081, api_keys=[token], cookie_file=None,
              auth_user=None, xsrf_token=None, log_requests=False,
              retry_attempts=1, request_timeout_sec=80, temporary_chats=True)
ThreadedServer(('0.0.0.0', 8081), GeminiHandler).serve_forever()
