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
from .session_audit import AUTH_COOKIES, error_type, session_event

SESSION_ROTATE_INTERVAL = 10 * 60
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

    def request(self, client, config, endpoint, method, url, **kwargs):
        started = time.monotonic()
        try:
            before = {item.name: item.value for item in client.cookies.jar}
        except Exception:
            before = {}
        try:
            reply = getattr(client, method)(url, **kwargs)
        except Exception as error:
            session_event('network_error', self.config_path, config, endpoint=endpoint,
                          elapsed_ms=(time.monotonic() - started) * 1000, error_type=error_type(error))
            raise
        try:
            after = {item.name: item.value for item in client.cookies.jar if not item.is_expired()}
            changed = [name for name in AUTH_COOKIES if name in after and before.get(name) != after[name]]
            removed = [name for name in AUTH_COOKIES if name in before and name not in after]
            target = urlparse(reply.headers.get('Location', ''))
            redirect = ('google_login' if target.hostname == 'accounts.google.com' else
                        'gemini_app' if target.hostname == 'gemini.google.com' else 'other')
            session_event('google_response', self.config_path, config, endpoint=endpoint,
                          status=reply.status_code, elapsed_ms=(time.monotonic() - started) * 1000,
                          changed_auth_cookies=changed, removed_auth_cookies=removed,
                          **({'redirect': redirect} if reply.is_redirect else {}),
                          throttle=300 if reply.status_code == 200 and endpoint != 'rotate_cookies' and not changed and not removed else 0)
        except Exception:
            pass  # Best-effort diagnostics cannot alter the HTTP operation.
        return reply

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
        reply = self.request(client, config, 'gemini_page', 'get', 'https://gemini.google.com' + prefix + '/app')
        if reply.status_code in (301, 302, 303, 307, 308):
            target = urlparse(reply.headers.get('Location', ''))
            match = re.fullmatch(r'(/u/\d+)?/app/?', target.path)
            if target.scheme == 'https' and target.netloc == 'gemini.google.com' and match:
                prefix = match.group(1) or ''
                reply = self.request(client, config, 'gemini_page', 'get', 'https://gemini.google.com' + prefix + '/app')
                if reply.status_code in (301, 302, 303, 307, 308):
                    session_event('auth_failure', self.config_path, config, reason='redirect_loop')
                    raise UsageAuthError('Google session requires login')
            else:
                session_event('auth_failure', self.config_path, config, reason='login_redirect')
                raise UsageAuthError('Google session requires login')
        reply.raise_for_status()
        fields = {}
        for name in ('SNlM0e', 'cfb2h', 'FdrFJe', 'oPEP7c'):
            match = re.search(r'"' + name + r'"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', reply.text)
            if match:
                fields[name] = json.loads('"' + match.group(1) + '"')
        if not fields.get('SNlM0e'):
            session_event('auth_failure', self.config_path, config, reason='missing_xsrf', has_xsrf=False)
            raise UsageAuthError('Google session requires login')
        fields['_account_prefix'] = prefix
        email = fields.get('oPEP7c')
        if config.get('email') and email and email.casefold() != config['email'].casefold():
            session_event('auth_failure', self.config_path, config, reason='identity_mismatch', identity_matches=False)
            raise UsageAuthError('Google account identity mismatch')
        session_event('auth_ready', self.config_path, config, has_xsrf=True, has_identity=bool(email), throttle=300)
        return fields

    def persist(self, config, cookie_path, original, client, fields=None, rotated=False):
        # The client starts with every stored cookie. Rebuild from its current
        # jar so a Set-Cookie deletion cannot resurrect an expired credential.
        pairs = {}
        for item in client.cookies.jar:
            if item.domain.lstrip('.') in ('google.com', 'gemini.google.com') and not item.is_expired():
                pairs[item.name] = item.value
        with private_lock(self.config_path.with_suffix('.lock')):
            latest = json.loads(self.config_path.read_text(encoding='utf-8'))
            if cookie_path.read_text(encoding='utf-8').strip() != original:
                session_event('cookie_save_conflict', self.config_path, latest)
                return  # A manual cookie update wins over an in-flight refresh.
            updated = header_cookie(pairs)
            atomic_text(cookie_path, updated)
            previous = cookie_pairs(original)
            changed = [name for name in AUTH_COOKIES if name in pairs and previous.get(name) != pairs[name]]
            removed = [name for name in AUTH_COOKIES if name in previous and name not in pairs]
            if changed or removed:
                session_event('cookie_saved', self.config_path, latest,
                              changed_auth_cookies=changed, removed_auth_cookies=removed)
            if fields is None:
                return updated
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
            if rotated:
                session_event('rotation_success', self.config_path, latest)
        self.fields = fields
        self.fingerprint = hashlib.sha256(header_cookie(pairs).encode()).hexdigest()
        self.loaded_at = time.monotonic()
        return updated

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
        session_event('rotation_due', self.config_path, config,
                      rotation_age_seconds=time.time() - anchor,
                      overdue_seconds=max(0, time.time() - anchor - SESSION_ROTATE_INTERVAL))
        try:
            self.refresh(automatic=True, rotate=True)
        except (UsageAuthError, httpx.HTTPError) as error:
            # A maintenance failure must not discard a cookie that still authenticates.
            # The normal RPC still verifies login and performs its bounded repair.
            session_event('maintenance_error', self.config_path, config, error_type=error_type(error))

    def refresh(self, automatic=False, rotate=False):
        config, cookie_path, original, pairs, prefix = self.settings()
        session_event('refresh_start', self.config_path, config, automatic=automatic, rotate=rotate,
                      throttle=0 if rotate else 300)
        with self.client(pairs) as client:
            if not rotate:
                try:
                    fields = self.page(client, config, prefix)
                    self.persist(config, cookie_path, original, client, fields)
                    return
                except UsageAuthError:
                    pass
            # Ordinary page checks must not reset the rotation cooldown. The
            # 30-second poll otherwise postpones the 10-minute rotation forever.
            with private_lock(self.config_path.with_suffix('.lock')):
                latest = json.loads(self.config_path.read_text(encoding='utf-8'))
                if automatic and time.time() - latest.get('refresh_attempt_at', 0) < SESSION_REPAIR_COOLDOWN:
                    session_event('refresh_cooldown', self.config_path, latest,
                                  attempt_age_seconds=max(0, time.time() - latest.get('refresh_attempt_at', 0)), throttle=60)
                    raise UsageAuthError('Session repair is cooling down; import a new cookie JSON if login was revoked')
                latest['refresh_attempt_at'] = time.time()
                write_json(self.config_path, latest)
            response = self.request(client, latest, 'rotate_cookies', 'post', 'https://accounts.google.com/RotateCookies',
                headers={'Origin': 'https://accounts.google.com', 'Content-Type': 'application/json'},
                content='[000,"-0000000000000000000"]')
            if response.status_code in (400, 401, 403):
                session_event('auth_failure', self.config_path, latest, endpoint='rotate_cookies',
                              reason='http_auth_rejected', status=response.status_code)
                raise UsageAuthError('Google could not renew this session; import a new cookie JSON')
            response.raise_for_status()
            # A successful RotateCookies can invalidate the previous timestamp
            # cookie. Save its replacement before another network request.
            original = self.persist(config, cookie_path, original, client)
            if original is None:
                return
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
                    original = self.persist(config, cookie_path, original, client, fields)
                    if original is None:
                        raise UsageAuthError('Google session changed during request')
                fields = self.fields
                prefix = fields.get('_account_prefix', prefix)
                params = {'rpcids': rpcid, 'hl': 'en', 'rt': 'c', 'source-path': prefix + source,
                          '_reqid': str(int(time.time()) % 1000000)}
                if fields.get('cfb2h'):
                    params['bl'] = fields['cfb2h']
                if fields.get('FdrFJe'):
                    params['f.sid'] = fields['FdrFJe']
                endpoint = {'jSf9Qc': 'quota_rpc', 'otAQ7b': 'models_rpc'}.get(rpcid, 'other_rpc')
                response = self.request(client, config, endpoint, 'post', 'https://gemini.google.com' + prefix + '/_/BardChatUi/data/batchexecute',
                    params=params, data={'at': fields['SNlM0e'], 'f.req': json.dumps([[[rpcid, payload, None, 'generic']]])},
                    headers={'Origin': 'https://gemini.google.com', 'Referer': 'https://gemini.google.com' + prefix + '/app',
                             'X-Same-Domain': '1', 'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8',
                             'x-goog-ext-525001261-jspb': '[1,null,null,null,null,null,null,null,[4,5,6,8],null,null,null,null,null,null,null]',
                             'x-goog-ext-73010989-jspb': '[0]'})
                if response.status_code in (400, 401, 403):
                    session_event('auth_failure', self.config_path, config, endpoint=endpoint,
                                  reason='http_auth_rejected', status=response.status_code)
                    raise UsageAuthError('Google rejected this session')
                response.raise_for_status()
                try:
                    rpc_bodies(response.text, rpcid)  # Authentication rejection even under HTTP 200.
                except UsageAuthError:
                    session_event('auth_failure', self.config_path, config, endpoint=endpoint, reason='rpc_auth_rejected')
                    raise
                self.persist(config, cookie_path, original, client, fields)
                return response.text
        except UsageAuthError:
            if not retry:
                raise
            self.fields = {}
            self.refresh(automatic=True, rotate=True)
            return self.request_rpc(rpcid, payload, source, retry=False)
