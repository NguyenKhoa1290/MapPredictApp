"""Configuration management."""
import json
import os
from collections.abc import MutableMapping
from contextlib import contextmanager
from contextvars import ContextVar

DEFAULT_CONFIG = {
    "port": 8081,
    "host": "0.0.0.0",
    "retry_attempts": 3,
    "retry_delay_sec": 2,
    "request_timeout_sec": 180,
    "gemini_bl": "boq_assistant-bard-web-server_20260716.08_p0",
    "auth_user": None,
    "xsrf_token": None,
    "default_model": "gemini-3.6-flash",
    "log_requests": True,
    "cookie_file": None,
    "proxy": None,
    "api_keys": [],
    "temporary_chats": False,
}

class RequestConfig(MutableMapping):
    """Process defaults with an isolated copy for each concurrent generation."""
    def __init__(self, defaults):
        self.defaults = dict(defaults)
        self.local = ContextVar('gemini_request_config', default=None)

    def values_for_request(self):
        current = self.local.get()
        return self.defaults if current is None else current

    def __getitem__(self, key):
        return self.values_for_request()[key]

    def __setitem__(self, key, value):
        self.values_for_request()[key] = value

    def __delitem__(self, key):
        del self.values_for_request()[key]

    def __iter__(self):
        return iter(self.values_for_request())

    def __len__(self):
        return len(self.values_for_request())

    @contextmanager
    def isolated(self):
        token = self.local.set(dict(self))
        try:
            yield self
        finally:
            self.local.reset(token)


CONFIG = RequestConfig(DEFAULT_CONFIG)


def load_config(path: str = None):
    """Load config from JSON file."""
    if path and os.path.exists(path):
        with open(path) as f:
            CONFIG.update(json.load(f))
    return CONFIG


def find_config():
    """Search for config file in standard locations."""
    for p in ["./config.json", os.path.expanduser("~/.config/gemini-web2api/config.json")]:
        if os.path.exists(p):
            return p
    return None
