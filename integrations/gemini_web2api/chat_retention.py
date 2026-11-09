"""Delete only application-created Google chats after their group becomes idle."""
import hashlib
import json
import os
from pathlib import Path
import re
import time

from .google_session import GoogleSession, rpc_bodies, write_json
from .session_audit import emit, error_type

IDLE_SECONDS = max(60, int(os.environ.get('GEMINI_CHAT_IDLE_SECONDS', '3600')))


def group_key(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


class ChatRetention:
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.path = self.config_path.with_name('application-chats.json')

    def load(self):
        return json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}

    def touch(self, group, cid=None, now=None):
        rows = self.load()
        row = rows.setdefault(group_key(group), {'chats': [], 'last_used': 0})
        row['last_used'] = time.time() if now is None else now
        if isinstance(cid, str) and re.fullmatch(r'c_[A-Za-z0-9_-]{1,200}', cid) and cid not in row['chats']:
            row['chats'].append(cid)
        write_json(self.path, rows)

    def observer(self, group):
        pending = b''
        seen = set()
        def feed(chunk):
            nonlocal pending
            pending += chunk
            lines = pending.split(b'\n')
            pending = lines.pop()
            for line in lines:
                try:
                    for frame in json.loads(line):
                        if frame[0] != 'wrb.fr' or not isinstance(frame[2], str):
                            continue
                        cid = json.loads(frame[2])[1][0]
                        if isinstance(cid, str) and re.fullmatch(r'c_[A-Za-z0-9_-]{1,200}', cid) and cid not in seen:
                            self.touch(group, cid)
                            seen.add(cid)
                except (ValueError, TypeError, IndexError, KeyError):
                    continue
        return feed

    def cleanup(self, now=None, limit=5):
        rows = self.load()
        now = time.time() if now is None else now
        session = GoogleSession(self.config_path)
        deleted = 0
        for group, row in list(rows.items()):
            if now - row['last_used'] < IDLE_SECONDS:
                continue
            for cid in list(row['chats']):
                if deleted >= limit:
                    return deleted
                try:
                    # Google Web uses a delete RPC followed by a history mutation.
                    for rpc, payload in (('GzXR5e', [cid]), ('qWymEb', [cid, [1, None, 0, 1]])):
                        result = session.request_rpc(rpc, json.dumps(payload), source='/app', retry=False)
                        if not rpc_bodies(result, rpc):
                            raise ValueError('Missing deletion acknowledgement')
                    row['chats'].remove(cid)
                    deleted += 1
                    write_json(self.path, rows)
                    emit('chat_cleanup_complete', self.config_path)
                except Exception as error:
                    emit('chat_cleanup_error', self.config_path, error_type=error_type(error))
                    # Retain pending IDs across restarts and retry on the next tick.
                    return deleted
            if not row['chats']:
                del rows[group]
                write_json(self.path, rows)
        return deleted
