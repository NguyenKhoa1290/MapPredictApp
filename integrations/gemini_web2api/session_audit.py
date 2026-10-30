"""Bounded session diagnostics. No raw messages, URLs, identities or secrets."""
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import os
from pathlib import Path
import re
import threading
import time
import uuid

RUN_ID = uuid.uuid4().hex[:12]
AUTH_COOKIES = frozenset(('SID', 'SAPISID', 'APISID', 'HSID', 'SSID', 'NID',
    '__Secure-1PSID', '__Secure-3PSID', '__Secure-1PSIDTS', '__Secure-3PSIDTS',
    '__Secure-1PSIDCC', '__Secure-3PSIDCC', 'SIDCC'))
EVENTS = frozenset(('service_start', 'maintenance_tick', 'maintenance_complete', 'maintenance_error',
    'baseline', 'rotation_due', 'refresh_start', 'refresh_cooldown', 'google_response',
    'network_error', 'auth_failure', 'auth_ready', 'cookie_saved', 'cookie_save_conflict',
    'rotation_success', 'cookie_import', 'account_scan', 'generation_start', 'generation_response', 'generation_complete', 'generation_error'))
ENUMS = {
    'endpoint': {'gemini_page', 'rotate_cookies', 'quota_rpc', 'models_rpc', 'other_rpc', 'generate'},
    'reason': {'login_redirect', 'redirect_loop', 'missing_xsrf', 'identity_mismatch',
               'rpc_auth_rejected', 'http_auth_rejected', 'cookie_parse_error'},
    'redirect': {'google_login', 'gemini_app', 'other'},
    'state': {'ready', 'needs_login', 'unavailable', 'model_unavailable', 'exhausted', 'needs_attention'},
    'error_type': {'UsageAuthError', 'ReadTimeout', 'ConnectTimeout', 'WriteTimeout', 'PoolTimeout',
                   'ConnectError', 'ReadError', 'WriteError', 'RemoteProtocolError', 'HTTPStatusError',
                   'FileNotFoundError', 'PermissionError', 'TimeoutError', 'ValueError', 'HTTPError',
                   'URLError', 'SSLError', 'OtherError'},
}
NUMBERS = frozenset(('status', 'elapsed_ms', 'last_checked_at', 'last_rotated_at',
    'last_attempt_at', 'rotation_age_seconds', 'attempt_age_seconds', 'overdue_seconds',
    'poll_interval_seconds', 'rotate_interval_seconds', 'repair_cooldown_seconds', 'account_count'))
BOOLEANS = frozenset(('automatic', 'rotate', 'has_xsrf', 'has_identity', 'identity_matches', 'has_answer'))
_lock = threading.RLock()
_handlers = {}
_recent = {}


class PrivateHandler(RotatingFileHandler):
    def _open(self):
        fd = os.open(self.baseFilename, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        return os.fdopen(fd, 'a', encoding='utf-8')

    def handleError(self, record):
        pass  # A full diagnostics disk must not break Google session maintenance.


def audit_path():
    folder = os.environ.get('GEMINI_STATE_DIR')
    return Path(folder) / 'diagnostics' / 'session.jsonl' if folder else None


def error_type(error):
    name = type(error).__name__
    return name if name in ENUMS['error_type'] else 'OtherError'


def emit(event, config_path=None, *, throttle=0, **fields):
    """Only allow fixed schemas; never serialize caller exceptions or dicts."""
    try:
        destination = audit_path()
        if destination is None or event not in EVENTS:
            return False
        account = Path(config_path).parent.name if config_path else 'service'
        if not re.fullmatch(r'[0-9a-f]{32}', account):
            account = 'legacy' if config_path else 'service'
        record = {'ts_utc': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                  'run_id': RUN_ID, 'account': account, 'event': event}
        for key, value in fields.items():
            if key in ENUMS and isinstance(value, str) and value in ENUMS[key]:
                record[key] = value
            elif key in NUMBERS and type(value) in (int, float) and math.isfinite(value) and value >= 0:
                record[key] = round(value, 3)
            elif key in BOOLEANS and type(value) is bool:
                record[key] = value
            elif key == 'generation' and isinstance(value, str) and re.fullmatch(r'[0-9a-f]{12}', value):
                record[key] = value
            elif key in ('changed_auth_cookies', 'removed_auth_cookies', 'received_auth_cookies') and isinstance(value, (list, tuple, set)):
                record[key] = sorted(name for name in AUTH_COOKIES if name in value)
        with _lock:
            stamp = (str(destination), account, event, record.get('endpoint'), record.get('state'))
            if throttle and time.monotonic() - _recent.get(stamp, -1e12) < throttle:
                return False
            handler = _handlers.get(str(destination))
            if handler is None:
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                handler = PrivateHandler(destination, maxBytes=2 * 1024 * 1024, backupCount=4, delay=True)
                handler.setFormatter(logging.Formatter('%(message)s'))
                _handlers[str(destination)] = handler
            handler.handle(logging.LogRecord('gemini.session.audit', logging.INFO, '', 0,
                           json.dumps(record, ensure_ascii=True), (), None))
            _recent[stamp] = time.monotonic()
        return True
    except Exception:
        return False


def session_event(event, config_path, config=None, **fields):
    config = config or {}
    return emit(event, config_path, generation=config.get('audit_generation'),
                last_checked_at=config.get('session_checked_at'),
                last_rotated_at=config.get('session_rotated_at'),
                last_attempt_at=config.get('refresh_attempt_at'), **fields)
