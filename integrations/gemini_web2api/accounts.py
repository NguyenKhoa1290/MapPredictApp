"""Isolated Google accounts, manual selection, and account-scoped quotas."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import time
import uuid

from .gemini_usage import UsageReader, UsageAuthError
from .google_session import GoogleSession, atomic_text, cookie_pairs, header_cookie, private_lock, rpc_bodies, write_json

SESSION_KEYS = ('auth_user', 'xsrf_token', 'gemini_bl', 'model_headers', 'extra_models', 'email', 'model_available')


class AccountMismatchError(ValueError):
    """A replacement cookie belongs to a different verified Google account."""


class AccountStore:
    def __init__(self, root):
        self.root = Path(root)
        self.registry_path = self.root / 'secrets/accounts.json'
        self.lock_path = self.root / 'secrets/accounts.lock'
        self.readers = {}

    def registry(self):
        if not self.registry_path.exists():
            return {'accounts': []}
        return json.loads(self.registry_path.read_text(encoding='utf-8'))

    def path(self, account_id):
        if not re.fullmatch(r'[0-9a-f]{32}', account_id):
            raise ValueError('Invalid account identifier')
        return self.root / 'secrets/accounts' / account_id / 'config.json'

    def initialize(self):
        with private_lock(self.lock_path):
            if self.registry_path.exists():
                return
            current = json.loads((self.root / 'secrets/config.json').read_text(encoding='utf-8'))
            cookie_path = Path(current.get('cookie_file') or self.root / 'secrets/cookie.txt')
            pairs = cookie_pairs(cookie_path.read_text(encoding='utf-8'))
            account_id = uuid.uuid4().hex
            profile = self.path(account_id)
            profile_cookie = profile.with_name('cookie.txt')
            atomic_text(profile_cookie, header_cookie(pairs))
            settings = {key: current[key] for key in SESSION_KEYS if key in current}
            settings.update(cookie_file=str(profile_cookie), label='Tài khoản 1')
            write_json(profile, settings)
            write_json(self.registry_path, {'accounts': [{'id': account_id, 'label': settings['label']}]})

    def add_cookie(self, text, label=None, auth_user=None, update_id=None):
        pairs = cookie_pairs(text)
        self.initialize()
        digest = hashlib.sha256(pairs['__Secure-1PSID'].encode()).hexdigest()
        with private_lock(self.lock_path):
            registry = self.registry()
            if update_id and not any(item['id'] == update_id for item in registry['accounts']):
                raise ValueError('Unknown account')
            matches = []
            for entry in registry['accounts']:
                profile = json.loads(self.path(entry['id']).read_text(encoding='utf-8'))
                old = cookie_pairs(Path(profile['cookie_file']).read_text(encoding='utf-8'))
                if hashlib.sha256(old['__Secure-1PSID'].encode()).hexdigest() == digest:
                    matches.append((entry, profile))
            if not update_id:
                default_matches = [entry for entry, profile in matches if profile.get('auth_user') is None]
                if len(default_matches) == 1:
                    update_id = default_matches[0]['id']
                elif len(matches) == 1:
                    update_id = matches[0][0]['id']
            account_id = update_id or uuid.uuid4().hex
            profile_path = self.path(account_id)
            previous = json.loads(profile_path.read_text(encoding='utf-8')) if profile_path.exists() else {}
            if auth_user is None and previous:
                auth_user = previous.get('auth_user')
            if update_id and previous.get('email') and not any(entry['id'] == update_id for entry, _ in matches):
                verifier = GoogleSession(profile_path)
                prefix = f'/u/{auth_user}' if auth_user is not None and auth_user != '' else ''
                try:
                    with verifier.client(pairs) as client:
                        verifier.page(client, previous, prefix)
                except UsageAuthError as exc:
                    if 'identity mismatch' in str(exc):
                        raise AccountMismatchError('Cookie belongs to a different Google account') from None
                    raise
            label = label or previous.get('label') or f'Tài khoản {len(registry["accounts"]) + 1}'
            # Old tokens/model identity must not be transferred to a newly pasted session.
            profile = {'label': label, 'auth_user': auth_user, 'cookie_file': str(profile_path.with_name('cookie.txt'))}
            # Identity was checked above, or the cookie digest is unchanged.
            if previous.get('email'):
                profile['email'] = previous['email']
            atomic_text(profile_path.with_name('cookie.txt'), header_cookie(pairs))
            write_json(profile_path, profile)
            if not update_id:
                registry['accounts'].append({'id': account_id, 'label': label})
            else:
                next(item for item in registry['accounts'] if item['id'] == account_id)['label'] = label
            write_json(self.registry_path, registry)
        return account_id

    def discover(self, account_id):
        path = self.path(account_id)
        session = GoogleSession(path)
        bodies = rpc_bodies(session.request_rpc('otAQ7b', source='/app'), 'otAQ7b')
        routes = None
        for body in bodies:
            if not isinstance(body, list) or len(body) <= 17 or not isinstance(body[15], list):
                continue
            tier = body[16] if isinstance(body[16], list) else []
            caps = body[17] if isinstance(body[17], list) else []
            if 21 in tier:
                capacity, field = 1, 13
            elif 22 in tier:
                capacity, field = 2, 13
            elif 115 in caps:
                capacity, field = 4, 12
            elif 16 in tier or 106 in caps:
                capacity, field = 3, 12
            else:
                capacity, field = (2, 12) if 8 in tier or 19 in caps else (1, 12)
            for model in body[15]:
                if not isinstance(model, list):
                    continue
                def value(index):
                    return model[index] if len(model) > index else None
                category = value(1) or value(10) or ''
                display = value(11) or value(19) or category
                if 'argon' not in (str(category) + ' ' + str(display)).casefold():
                    continue
                number = value(17) if type(value(17)) is int else value(9)
                if type(number) is not int or not isinstance(value(0), str):
                    continue
                header = [1, None, None, None, value(0), None, None, 0, [4,5,6,8], None, None, None, None, None, number]
                header[field - 1] = capacity
                routes = ({'gemini-4-argon': {'mode': number, 'think': 4, 'desc': str(display)}},
                          {str(number): {'x-goog-ext-525001261-jspb': json.dumps(header),
                                         'x-goog-ext-73010989-jspb': '[0]', 'x-goog-ext-73010990-jspb': '[0,0,0]'}})
        with private_lock(path.with_suffix('.lock')):
            config = json.loads(path.read_text(encoding='utf-8'))
            config['model_available'] = routes is not None
            config['model_checked_at'] = time.time()
            if routes:
                config['extra_models'], config['model_headers'] = routes
            write_json(path, config)
        return routes is not None

    def scan_one(self, entry, discover=False):
        account_id = entry['id']
        result = {'id': account_id, 'label': entry['label'], 'usage': None, 'status': 'unavailable', 'email': None}
        try:
            path = self.path(account_id)
            config = json.loads(path.read_text(encoding='utf-8'))
            result['email'] = config.get('email')
            if discover or time.time() - config.get('model_checked_at', 0) > 3600:
                self.discover(account_id)
            reader = self.readers.setdefault(account_id, UsageReader(self.root, config_path=path))
            result['usage'] = reader.fetch()
            config = json.loads(path.read_text(encoding='utf-8'))
            result['email'] = config.get('email')
            result['model_available'] = config.get('model_available', False)
            if not result['model_available']:
                result['status'] = 'model_unavailable'
            elif any((window.get('used_fraction') or 0) >= 1 for window in result['usage'].values() if isinstance(window, dict)):
                result['status'] = 'exhausted'
            else:
                result['status'] = 'ready'
        except UsageAuthError:
            result['status'] = 'needs_login'
        except Exception:
            result['status'] = 'unavailable'
        return result

    def scan(self, discover=False):
        self.initialize()
        entries = self.registry()['accounts']
        with ThreadPoolExecutor(max_workers=min(4, max(1, len(entries)))) as pool:
            return list(pool.map(lambda item: self.scan_one(item, discover), entries))

    def activate(self, account_id):
        path = self.path(account_id)
        profile = json.loads(path.read_text(encoding='utf-8'))
        if not profile.get('model_available'):
            raise ValueError('Selected account has not verified Argon access; scan it first')
        with private_lock(self.lock_path):
            main_path = self.root / 'secrets/config.json'
            main = json.loads(main_path.read_text(encoding='utf-8'))
            # Preserve API keys and every existing route. Only account/session fields change.
            main.update({key: profile.get(key) for key in ('auth_user','xsrf_token','gemini_bl')})
            main['cookie_file'] = profile['cookie_file']
            main.setdefault('model_headers', {}).update(profile.get('model_headers', {}))
            main.setdefault('extra_models', {}).update(profile.get('extra_models', {}))
            main['active_account_id'] = account_id
            main['active_account_label'] = profile['label']
            write_json(main_path, main)
