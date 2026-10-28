"""Maintain one Google session without depending on browser traffic."""
import json
from pathlib import Path
import threading
import time

from .config import CONFIG
from .google_session import GoogleSession, UsageAuthError, cookie_pairs, header_cookie, write_json, atomic_text


class SessionManager:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / 'session.json'
        self.cookie = self.folder / 'cookies.txt'
        self.lock = threading.RLock()
        self.session = GoogleSession(self.path)
        self.stop = threading.Event()
        self.details = {'state': 'not_configured', 'checked_at': None, 'rotated_at': None,
                        'refresh_interval_hours': 12}
        if self.path.exists():
            self.activate()
            self.details['state'] = 'pending'

    def activate(self):
        settings = json.loads(self.path.read_text(encoding='utf-8'))
        if settings.get('xsrf_token'):
            for key in ('auth_user', 'xsrf_token', 'gemini_bl'):
                if key in settings:
                    CONFIG[key] = settings[key]
            CONFIG['cookie_file'] = str(self.cookie)
        else:
            # An unverified imported cookie must not break the anonymous route.
            CONFIG.update(cookie_file=None, auth_user=None, xsrf_token=None)
        self.details['checked_at'] = settings.get('session_checked_at')
        self.details['rotated_at'] = settings.get('session_rotated_at')

    def status(self):
        with self.lock:
            return dict(self.details)

    def refresh(self, rotate=False):
        with self.lock:
            if not self.path.exists():
                return self.status()
            try:
                if rotate:
                    self.session.refresh(rotate=True)
                else:
                    self.session.maintain()
                    self.session.refresh()
                self.activate()
                self.details.update(state='ready', attempt_at=time.time())
            except UsageAuthError:
                CONFIG.update(cookie_file=None, auth_user=None, xsrf_token=None)
                self.details.update(state='needs_attention', attempt_at=time.time())
            except Exception:
                # Never return exception text, cookies, account identity or XSRF tokens.
                self.details.update(state='needs_attention', attempt_at=time.time())
            return self.status()

    def import_cookie(self, content, account=None):
        if not isinstance(content, str) or not 1 <= len(content) <= 60000:
            raise ValueError('Invalid cookie content')
        pairs = cookie_pairs(content)
        if account is not None and (not isinstance(account, str) or not account.isdecimal() or len(account) > 2):
            raise ValueError('Invalid account index')
        with self.lock:
            atomic_text(self.cookie, header_cookie(pairs))
            write_json(self.path, {'cookie_file': str(self.cookie), 'auth_user': account,
                                  'session_maintenance_started_at': time.time()})
            self.session = GoogleSession(self.path)
            self.activate()
            return self.refresh()

    def start(self):
        def maintain():
            while not self.stop.is_set():
                if self.path.exists():
                    self.refresh()
                self.stop.wait(1200)
        threading.Thread(target=maintain, name='gemini-session-maintenance', daemon=True).start()
