"""Run the supplied Gemini adapter on the private Compose network."""
from pathlib import Path
import json
import os
from gemini_web2api.config import CONFIG
from gemini_web2api.server import GeminiHandler, ThreadedServer
from gemini_web2api.session_manager import SessionManager

token = Path('/run/secrets/assistant_key').read_text().strip()
CONFIG.update(host='0.0.0.0', port=8081, api_keys=[token], cookie_file=None,
              auth_user=None, xsrf_token=None, log_requests=False,
              retry_attempts=1, request_timeout_sec=80, temporary_chats=True)
manager = SessionManager(os.environ.get('GEMINI_STATE_DIR', '/tmp/gemini-session'))


class ManagedGeminiHandler(GeminiHandler):
    def session_request(self):
        if not self._authorized():
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        if self.command == 'GET' and self.path == '/_internal/session':
            self.send_json(manager.status())
            return
        if self.command != 'POST' or self.path not in ('/_internal/session/import', '/_internal/session/refresh'):
            self.send_json({'error': 'Not found'}, 404)
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 65536:
                raise ValueError()
            body = json.loads(self.rfile.read(length))
            result = manager.import_cookie(body['cookie'], body.get('account') or None) if self.path.endswith('/import') else manager.refresh(rotate=True)
            self.send_json(result)
        except (ValueError, KeyError, TypeError):
            self.send_json({'error': 'Cookie không hợp lệ'}, 400)

    def do_GET(self):
        if self.path.startswith('/_internal/'):
            self.session_request()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith('/_internal/'):
            self.session_request()
        else:
            super().do_POST()


if __name__ == '__main__':
    manager.start()
    ThreadedServer(('0.0.0.0', 8081), ManagedGeminiHandler).serve_forever()
