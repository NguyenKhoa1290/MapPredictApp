"""Run the supplied Gemini adapter on the private Compose network."""
from pathlib import Path
import json
import os
import threading
import time
import uuid
from gemini_web2api.config import CONFIG
from gemini_web2api.server import GeminiHandler, ThreadedServer
from gemini_web2api.session_manager import SessionManager
from gemini_web2api.account_pool import AccountPool, ARGON, FLASH
from gemini_web2api.quota_guard import QuotaRejected
from gemini_web2api.gemini import generate
from gemini_web2api.tools import messages_to_prompt
from gemini_web2api.google_session import SESSION_POLL_INTERVAL
from gemini_web2api.models import thinking_depth

token = Path('/run/secrets/assistant_key').read_text().strip()
CONFIG.update(host='0.0.0.0', port=8081, api_keys=[token], cookie_file=None,
              auth_user=None, xsrf_token=None, log_requests=False,
              retry_attempts=1, request_timeout_sec=80, temporary_chats=True)
manager = SessionManager(os.environ.get('GEMINI_STATE_DIR', '/tmp/gemini-session'))
pool = AccountPool(manager.folder, manager.lock)


class ManagedGeminiHandler(GeminiHandler):
    def session_request(self):
        if not self._authorized():
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        if self.command == 'GET' and self.path == '/_internal/session':
            self.send_json(manager.status())
            return
        if self.command == 'GET' and self.path == '/_internal/accounts':
            self.send_json(pool.snapshot())
            return
        if self.command == 'GET' and self.path == '/_internal/argon-availability':
            self.send_json(pool.availability())
            return
        if self.command != 'POST' or self.path not in ('/_internal/session/import', '/_internal/session/refresh', '/_internal/accounts/import', '/_internal/accounts/scan', '/_internal/accounts/refresh'):
            self.send_json({'error': 'Not found'}, 404)
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 65536:
                raise ValueError()
            body = json.loads(self.rfile.read(length))
            if self.path == '/_internal/accounts/import':
                result = pool.import_cookie(body['cookie'], body.get('label', ''), body.get('account') or None, body.get('account_id') or None)
            elif self.path == '/_internal/accounts/scan':
                result = pool.scan()
            elif self.path == '/_internal/accounts/refresh':
                result = pool.refresh()
            else:
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
            # Managed pools reject a concurrent generation instead of queuing it
            # behind an abandoned request whose caller already timed out.
            super().do_POST()

    def _handle_chat(self, body):
        request = self._parse_body(body)
        if not isinstance(request, dict) or request.get('model') not in (ARGON, FLASH):
            with manager.lock:
                return super()._handle_chat(body)
        model = request['model']
        try:
            thinking_depth(request.get('reasoning_effort'), 1)
        except ValueError as error:
            self.send_json({'error': {'message': str(error)}}, 400)
            return
        if request.get('stream') or request.get('tools'):
            self.send_json({'error': {'code': 'unsupported_argon_request', 'message': 'Thông minh chỉ nhận chat không streaming'}}, 400)
            return
        prompt, images = messages_to_prompt(request.get('messages', []))
        if not prompt.strip() or images:
            self.send_json({'error': {'message': 'Thông minh nhận nội dung văn bản đã tóm tắt'}}, 400)
            return
        try:
            reasoning = {}
            level = thinking_depth(request.get('reasoning_effort'), 1)
            def generate_argon(mode, think):
                text = generate(prompt, mode, level, metadata=reasoning)
                if reasoning.get('applied_level', None if model == FLASH else level) != level:
                    raise ValueError('Argon thinking level was not honored')
                return text
            if model == FLASH:
                try:
                    budget = max(1, min(120, float(getattr(self, 'headers', {}).get('X-Map-Predict-Timeout', 120))))
                except (ValueError, TypeError):
                    budget = 120
                text = pool.run_flash(generate_argon, timeout=budget)
            else:
                text = pool.run(generate_argon)
            self.send_json({'id': 'chatcmpl-' + uuid.uuid4().hex, 'object': 'chat.completion',
                            'created': int(time.time()), 'model': model,
                            'reasoning': reasoning,
                            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}]})
        except QuotaRejected as error:
            self.send_json(error.response(), error.status)


if __name__ == '__main__':
    manager.start()
    def maintain_accounts():
        while True:
            try:
                pool.scan(discover=False)
            except Exception:
                pass
            time.sleep(SESSION_POLL_INTERVAL)
    threading.Thread(target=maintain_accounts, name='argon-account-maintenance', daemon=True).start()
    ThreadedServer(('0.0.0.0', 8081), ManagedGeminiHandler).serve_forever()
