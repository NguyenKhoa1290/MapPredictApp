"""Route Argon across verified accounts, never across different models."""
from contextlib import contextmanager
import json
from pathlib import Path
import time

from .accounts import AccountStore
from .config import CONFIG
from .gemini_usage import UsageReader
from .google_session import write_json
from .quota_guard import QuotaGuard, QuotaRejected

ARGON = 'gemini-4-argon'
SESSION_FIELDS = ('cookie_file', 'auth_user', 'xsrf_token', 'gemini_bl', 'model_headers', 'extra_models')


class AccountPool:
    def __init__(self, folder, lock):
        self.root = Path(folder) / 'pool'
        self.lock = lock
        secrets = self.root / 'secrets'
        secrets.mkdir(parents=True, exist_ok=True)
        for name, content in (('config.json', {}), ('accounts.json', {'accounts': []})):
            path = secrets / name
            if not path.exists():
                write_json(path, content)
        self.store = AccountStore(self.root)
        self.rows = {}

    def snapshot(self):
        entries = self.store.registry()['accounts']
        return {'model': ARGON, 'policy': 'rotate_accounts_only', 'accounts': [
            {'id': entry['id'], 'label': entry['label'],
             **self.rows.get(entry['id'], {'status': 'not_checked', 'usage': None})}
            for entry in entries]}

    def scan(self):
        with self.lock:
            for entry in self.store.registry()['accounts']:
                row = self.store.scan_one(entry, discover=True)
                # Account identity, cookie paths and routing headers stay private.
                self.rows[entry['id']] = {key: row.get(key) for key in ('status', 'usage', 'model_available')}
            return self.snapshot()

    def import_cookie(self, text, label, account=None, account_id=None):
        if not isinstance(text, str) or not 1 <= len(text) <= 60000:
            raise ValueError('Invalid cookie')
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 80:
            raise ValueError('Invalid label')
        if account is not None and (not isinstance(account, str) or not account.isdecimal() or len(account) > 2):
            raise ValueError('Invalid account index')
        with self.lock:
            entries = self.store.registry()['accounts']
            if not account_id and len(entries) >= 8:
                raise ValueError('At most eight accounts')
            identifier = self.store.add_cookie(text, label.strip(), account, update_id=account_id)
            self.rows[identifier] = {'status': 'not_checked', 'usage': None}
            return self.snapshot()

    @contextmanager
    def profile(self, settings):
        previous = {key: CONFIG.get(key) for key in SESSION_FIELDS}
        try:
            CONFIG.update({key: settings.get(key) for key in SESSION_FIELDS})
            yield
        finally:
            CONFIG.update(previous)

    def run(self, generate):
        if not self.lock.acquire(blocking=False):
            raise QuotaRejected('Đang xử lý yêu cầu khác, hãy thử lại', code='accounts_busy')
        try:
            entries = self.store.registry()['accounts']
            if not entries:
                raise QuotaRejected('Chưa có tài khoản cho Pro 4 Argon', status=503, code='accounts_unavailable')
            exhausted = 0
            deadline = time.monotonic() + 120
            for entry in entries:
                if time.monotonic() >= deadline:
                    break
                identifier = entry['id']
                try:
                    path = self.store.path(identifier)
                    settings = json.loads(path.read_text(encoding='utf-8'))
                    if time.time() - settings.get('model_checked_at', 0) > 3600:
                        self.store.discover(identifier)
                    guard = QuotaGuard(UsageReader(self.root, config_path=path))
                    guard.check()  # Reject absent/invalid quota windows, not just exhausted ones.
                    settings = json.loads(path.read_text(encoding='utf-8'))
                    route = (settings.get('extra_models') or {}).get(ARGON)
                    headers = (settings.get('model_headers') or {}).get(str(route.get('mode'))) if route else None
                    if not settings.get('model_available') or not route or not headers or not settings.get('xsrf_token'):
                        raise ValueError('Argon access not verified')
                    with self.profile(settings):
                        result = generate(route['mode'], route.get('think', 4))
                        if not isinstance(result, str) or not result.strip():
                            raise ValueError('Empty upstream response')
                        # Hold the response until the post-generation quota check passes.
                        usage = guard.check()
                    self.rows[identifier] = {'status': 'ready', 'usage': usage, 'model_available': True}
                    return result
                except QuotaRejected as error:
                    if error.code == 'quota_exhausted':
                        exhausted += 1
                    self.rows[identifier] = {'status': 'exhausted' if error.code == 'quota_exhausted' else 'unavailable', 'usage': None}
                except Exception:
                    self.rows[identifier] = {'status': 'needs_attention', 'usage': None}
            if exhausted == len(entries):
                raise QuotaRejected('Tất cả tài khoản Pro 4 Argon đã hết quota, không hạ model', code='quota_exhausted')
            raise QuotaRejected('Không có tài khoản Pro 4 Argon được xác minh còn quota, kiểm tra cookie và quota trong quản trị',
                                status=503, code='quota_unverified')
        finally:
            self.lock.release()
