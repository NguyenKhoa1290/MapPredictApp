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

    def session(self, group):
        row = self.load().get(group_key(group), {})
        if time.time() - row.get('last_used', 0) >= IDLE_SECONDS:
            return None
        return row.get('session') or None

    def prepare(self, group):
        session = self.session(group)
        rows = self.load()
        if not session and group_key(group) in rows:
            rows[group_key(group)].pop('session', None)
            write_json(self.path, rows)
        self.touch(group)
        return session

    def update_session(self, group, cid, rid='', rcid='', token=''):
        self.touch(group, cid)
        rows = self.load()
        row = rows[group_key(group)]
        session = row.setdefault('session', {'cid': cid, 'turns': 0})
        if session['cid'] != cid:
            raise RuntimeError('Google returned a different conversation')
        for key, value in (('rid', rid), ('rcid', rcid), ('token', token)):
            if isinstance(value, str) and value:
                session[key] = value
        write_json(self.path, rows)

    def complete(self, group, model_mode=None):
        rows = self.load()
        row = rows.get(group_key(group), {})
        if row.get('session'):
            row['session']['turns'] = row['session'].get('turns', 0) + 1
            if model_mode is not None:
                row['session']['model_mode'] = model_mode
            write_json(self.path, rows)

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
                        payload = json.loads(frame[2])
                        cid = payload[1][0]
                        if isinstance(cid, str) and re.fullmatch(r'c_[A-Za-z0-9_-]{1,200}', cid):
                            rid = payload[1][1] if len(payload[1]) > 1 else ''
                            rcid = payload[4][0][0] if len(payload) > 4 and payload[4] else ''
                            token = payload[25] if len(payload) > 25 else ''
                            snapshot = (cid, rid, rcid, token if isinstance(token, str) else '')
                            if snapshot not in seen:
                                self.update_session(group, *snapshot)
                                seen.add(snapshot)
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
