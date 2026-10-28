"""Account-scoped Google session maintenance, with private atomic storage."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlparse

import httpx

SESSION_ROTATE_INTERVAL = 12 * 60 * 60
SESSION_REPAIR_COOLDOWN = 300
SESSION_POLL_INTERVAL = 30


def maintenance_policy():
    return {'poll_interval_seconds': SESSION_POLL_INTERVAL,
            'rotate_interval_seconds': SESSION_ROTATE_INTERVAL,
            'repair_cooldown_seconds': SESSION_REPAIR_COOLDOWN}


class UsageAuthError(ValueError):
    pass


@contextlib.contextmanager
def private_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        deadline = time.monotonic() + 45
        while True:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise TimeoutError('Account file is busy') from None
                time.sleep(.1)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp = tempfile.mkstemp(prefix='.update-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='') as stream:
            stream.write(text)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_json(path, data):
    atomic_text(path, json.dumps(data, indent=2, ensure_ascii=True))


def cookie_pairs(text):
    text = text.strip()
    if text.startswith('['):
        items = json.loads(text)
        pairs = {item['name']: item['value'] for item in items
                 if str(item.get('domain', '')).lstrip('.') in ('google.com', 'gemini.google.com')}
    elif text.startswith('{'):
        pairs = cookie_pairs(json.loads(text).get('cookie', ''))
    else:
        text = re.sub(r'^Cookie:\s*', '', text, flags=re.I)
        pairs = dict(part.strip().split('=', 1) for part in text.split(';') if '=' in part)
    if not {'SID', 'SAPISID', '__Secure-1PSID'}.issubset(pairs):
        raise ValueError('Missing required Google cookies')
    for name, value in pairs.items():
        if not isinstance(name, str) or not isinstance(value, str) or any(c in name + value for c in '\r\n;'):
            raise ValueError('Invalid cookie format')
    return pairs


def header_cookie(pairs):
    return '; '.join(f'{key}={value}' for key, value in pairs.items())


def rpc_bodies(text, rpcid):
    found = []
    def walk(value):
        if not isinstance(value, list):
            return
        if len(value) > 2 and value[:2] == ['wrb.fr', rpcid]:
            if len(value) > 5 and isinstance(value[5], list) and value[5] and value[5][0] == 7:
                raise UsageAuthError('Google session not accepted')
            if isinstance(value[2], str):
                found.append(json.loads(value[2]))
        else:
            for child in value:
                walk(child)
    for line in text.splitlines():
        try:
            walk(json.loads(line))
        except UsageAuthError:
            raise
        except (TypeError, ValueError):
            pass
    return found


class GoogleSession:
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.fields = {}
        self.fingerprint = None
        self.loaded_at = 0

    def settings(self):
        config = json.loads(self.config_path.read_text(encoding='utf-8'))
        cookie_path = Path(config['cookie_file'])
        text = cookie_path.read_text(encoding='utf-8').strip()
        pairs = cookie_pairs(text)
        account = config.get('auth_user')
        prefix = f'/u/{account}' if account is not None and account != '' else ''
        return config, cookie_path, text, pairs, prefix

    @contextlib.contextmanager
    def client(self, pairs):
        cookies = httpx.Cookies()
        for name, value in pairs.items():
            cookies.set(name, value, domain='.google.com', path='/')
        with httpx.Client(cookies=cookies, follow_redirects=False, timeout=15, trust_env=False,
                          headers={'User-Agent': 'Mozilla/5.0'}) as client:
            yield client

    def page(self, client, config, prefix):
        reply = client.get('https://gemini.google.com' + prefix + '/app')
        if reply.status_code in (301, 302, 303, 307, 308):
            target = urlparse(reply.headers.get('Location', ''))
            match = re.fullmatch(r'(/u/\d+)?/app/?', target.path)
            if target.scheme == 'https' and target.netloc == 'gemini.google.com' and match:
                prefix = match.group(1) or ''
                reply = client.get('https://gemini.google.com' + prefix + '/app')
                if reply.status_code in (301, 302, 303, 307, 308):
                    raise UsageAuthError('Google session requires login')
            else:
                raise UsageAuthError('Google session requires login')
        reply.raise_for_status()
        fields = {}
        for name in ('SNlM0e', 'cfb2h', 'FdrFJe', 'oPEP7c'):
            match = re.search(r'"' + name + r'"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', reply.text)
            if match:
                fields[name] = json.loads('"' + match.group(1) + '"')
        if not fields.get('SNlM0e'):
            raise UsageAuthError('Google session requires login')
        fields['_account_prefix'] = prefix
        email = fields.get('oPEP7c')
        if config.get('email') and email and email.casefold() != config['email'].casefold():
            raise UsageAuthError('Google account identity mismatch')
        return fields

    def persist(self, config, cookie_path, original, client, fields, rotated=False):
        pairs = cookie_pairs(original)
        for item in client.cookies.jar:
            if item.domain.lstrip('.') in ('google.com', 'gemini.google.com') and not item.is_expired():
                pairs[item.name] = item.value
        with private_lock(self.config_path.with_suffix('.lock')):
            latest = json.loads(self.config_path.read_text(encoding='utf-8'))
            if cookie_path.read_text(encoding='utf-8').strip() != original:
                return  # A manual cookie update wins over an in-flight refresh.
            atomic_text(cookie_path, header_cookie(pairs))
            latest['xsrf_token'] = fields['SNlM0e']
            if fields.get('cfb2h'):
                latest['gemini_bl'] = fields['cfb2h']
            if fields.get('oPEP7c'):
                latest['email'] = fields['oPEP7c']
            canonical = fields.get('_account_prefix')
            if canonical is not None:
                latest['auth_user'] = canonical.removeprefix('/u/') if canonical else None
            latest['session_checked_at'] = time.time()
            latest.setdefault('session_maintenance_started_at', time.time())
            if rotated:
                latest['session_rotated_at'] = time.time()
            write_json(self.config_path, latest)
        self.fields = fields
        self.fingerprint = hashlib.sha256(header_cookie(pairs).encode()).hexdigest()
        self.loaded_at = time.monotonic()

    def maintain(self):
        """Proactively rotate valid sessions; quota polling drives this for every account."""
        with private_lock(self.config_path.with_suffix('.lock')):
            config = json.loads(self.config_path.read_text(encoding='utf-8'))
            if 'session_maintenance_started_at' not in config:
                config['session_maintenance_started_at'] = time.time()
                write_json(self.config_path, config)
            anchor = config.get('session_rotated_at') or config['session_maintenance_started_at']
            if (time.time() - anchor < SESSION_ROTATE_INTERVAL or
                    time.time() - config.get('refresh_attempt_at', 0) < SESSION_REPAIR_COOLDOWN):
                return
        try:
            self.refresh(automatic=True, rotate=True)
        except (UsageAuthError, httpx.HTTPError):
            # A maintenance failure must not discard a cookie that still authenticates.
            # The normal RPC still verifies login and performs its bounded repair.
            pass

    def refresh(self, automatic=False, rotate=False):
        config, cookie_path, original, pairs, prefix = self.settings()
        with private_lock(self.config_path.with_suffix('.lock')):
            latest = json.loads(self.config_path.read_text(encoding='utf-8'))
            if automatic and time.time() - latest.get('refresh_attempt_at', 0) < SESSION_REPAIR_COOLDOWN:
                raise UsageAuthError('Session repair is cooling down; import a new cookie JSON if login was revoked')
            latest['refresh_attempt_at'] = time.time()
            write_json(self.config_path, latest)
        with self.client(pairs) as client:
            if not rotate:
                try:
                    fields = self.page(client, config, prefix)
                    self.persist(config, cookie_path, original, client, fields)
                    return
                except UsageAuthError:
                    pass
            response = client.post('https://accounts.google.com/RotateCookies',
                headers={'Origin': 'https://accounts.google.com', 'Content-Type': 'application/json'},
                content='[000,"-0000000000000000000"]')
            if response.status_code in (400, 401, 403):
                raise UsageAuthError('Google could not renew this session; import a new cookie JSON')
            response.raise_for_status()
            fields = self.page(client, config, prefix)
            self.persist(config, cookie_path, original, client, fields, rotated=True)

    def request_rpc(self, rpcid, payload='[]', source='/usage', retry=True):
        if retry:
            self.maintain()
        try:
            config, cookie_path, original, pairs, prefix = self.settings()
            digest = hashlib.sha256(header_cookie(pairs).encode()).hexdigest()
            with self.client(pairs) as client:
                if digest != self.fingerprint or not self.fields or time.monotonic() - self.loaded_at > 1200:
                    fields = self.page(client, config, prefix)
                    self.persist(config, cookie_path, original, client, fields)
                fields = self.fields
                prefix = fields.get('_account_prefix', prefix)
                params = {'rpcids': rpcid, 'hl': 'en', 'rt': 'c', 'source-path': prefix + source,
                          '_reqid': str(int(time.time()) % 1000000)}
                if fields.get('cfb2h'):
                    params['bl'] = fields['cfb2h']
                if fields.get('FdrFJe'):
                    params['f.sid'] = fields['FdrFJe']
                response = client.post('https://gemini.google.com' + prefix + '/_/BardChatUi/data/batchexecute',
                    params=params, data={'at': fields['SNlM0e'], 'f.req': json.dumps([[[rpcid, payload, None, 'generic']]])},
                    headers={'Origin': 'https://gemini.google.com', 'Referer': 'https://gemini.google.com' + prefix + '/app',
                             'X-Same-Domain': '1', 'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8',
                             'x-goog-ext-525001261-jspb': '[1,null,null,null,null,null,null,null,[4,5,6,8],null,null,null,null,null,null,null]',
                             'x-goog-ext-73010989-jspb': '[0]'})
                if response.status_code in (400, 401, 403):
                    raise UsageAuthError('Google rejected this session')
                response.raise_for_status()
                rpc_bodies(response.text, rpcid)  # Detect authentication rejection even under HTTP 200.
                return response.text
        except UsageAuthError:
            if not retry:
                raise
            self.fields = {}
            self.refresh(automatic=True, rotate=True)
            return self.request_rpc(rpcid, payload, source, retry=False)
