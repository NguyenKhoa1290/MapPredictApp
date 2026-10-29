"""Persistent AI configuration, private to the authenticated AI service."""
import copy
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from urllib.parse import urlsplit
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.request import Request, build_opener, ProxyHandler

from .prediction import PredictionError

LOCK = threading.RLock()
ARGON = 'gemini-4-argon'
FLASH = 'gemini-3.8-flash'


def is_argon(model):
    return model.split('@', 1)[0] == ARGON


def passcode_file(config):
    path = config.get('AI_SETTINGS_FILE')
    return Path(path).with_name('argon-passcode.hash') if path else None


def has_passcode(config):
    path = passcode_file(config)
    return bool(path and path.is_file() and path.read_text().startswith(('scrypt:', 'pbkdf2:')))


def set_passcode(config, value, disable=False):
    path = passcode_file(config)
    if not path:
        raise ValueError('Chưa cấu hình kho cài đặt AI')
    if not disable and (not isinstance(value, str) or not 8 <= len(value) <= 128):
        raise ValueError('Passcode cần từ 8 đến 128 ký tự')
    content = '' if disable else generate_password_hash(value)
    with LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.passcode-')
        try:
            with os.fdopen(descriptor, 'w') as stream:
                stream.write(content)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {'configured': bool(content)}


def authorize_pro(config, value):
    if not is_argon(config['ASSISTANT_MODEL']):
        return
    path = passcode_file(config)
    if not has_passcode(config):
        raise PredictionError('ARGON_DISABLED', 'Quản trị chưa đặt passcode cho Thông minh', 503)
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or not check_password_hash(path.read_text(), value):
        raise PredictionError('ARGON_PASSCODE_REQUIRED', 'Nhập passcode Thông minh do quản trị cấp', 403)


COOKIE_MESSAGE = 'Thông minh chưa có cookie hợp lệ hoặc cookie đã hết hạn, hãy cập nhật trong quản trị'


def argon_availability(config):
    try:
        key = Path(config['ASSISTANT_SECRET_FILE']).read_text().strip()
        base = config['ASSISTANT_URL'].rstrip('/').removesuffix('/v1')
        request = Request(base + '/_internal/argon-availability', headers={'Authorization': 'Bearer ' + key})
        with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
            result = json.loads(response.read(8192))
        if result.get('state') in ('ready', 'cookie_required'):
            return result['state']
    except Exception:
        pass
    return 'unknown'


def require_argon_cookie(config):
    if not is_argon(config['ASSISTANT_MODEL']) and config['ASSISTANT_MODEL'] != FLASH:
        return
    state = argon_availability(config)
    if state == 'cookie_required':
        raise PredictionError('COOKIE_REQUIRED', COOKIE_MESSAGE if is_argon(config['ASSISTANT_MODEL']) else 'Nhanh cần cookie tài khoản hợp lệ, hãy cập nhật trong quản trị', 503)
    if state != 'ready':
        raise PredictionError('COOKIE_UNVERIFIED', 'Chưa xác minh được cookie cho Thông minh, không chuyển sang Nhanh', 503)


def defaults(config):
    return {'models': {
        'fast': {'label': 'Nhanh', 'provider': 'gemini', 'model': FLASH,
                 'url': '', 'api_key': ''},
        'smart': {'label': 'Thông minh', 'provider': 'gemini', 'model': ARGON, 'url': '', 'api_key': ''}},
        'embedding': {'url': config.get('ASSISTANT_EMBEDDING_URL') or 'http://ai-embedding:11434',
                      'model': config['ASSISTANT_EMBEDDING_MODEL']}}


def load(config):
    result = defaults(config)
    path = config.get('AI_SETTINGS_FILE')
    with LOCK:
        if path and Path(path).is_file():
            saved = json.loads(Path(path).read_text(encoding='utf-8'))
            if 'fast' in saved.get('models', {}):
                result['models']['fast'].update(saved['models']['fast'])
                if result['models']['fast']['provider'] == 'gemini' and result['models']['fast']['model'] in ('gemini-3.6-flash', 'gemini-3.7-flash'):
                    result['models']['fast']['model'] = FLASH
            # Smart replaces the former separate Pro option, retaining its strict route.
            # Never restore the legacy thinking/Flash model or a third client option.
            result['embedding'].update(saved.get('embedding', {}))
    return result


def public(settings):
    result = copy.deepcopy(settings)
    for row in result['models'].values():
        row['has_api_key'] = bool(row.pop('api_key', ''))
    return result


def endpoint(value):
    if not isinstance(value, str) or len(value) > 500:
        raise ValueError('Địa chỉ service không hợp lệ')
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Dùng URL HTTP hoặc HTTPS, không đặt khóa trong URL')
    return value.rstrip('/')


def save(config, incoming):
    with LOCK:
        result = load(config)
        if not isinstance(incoming, dict) or set(incoming) != {'models', 'embedding'}:
            raise ValueError('Thiếu cấu hình model hoặc embedding')
        if not isinstance(incoming['models'], dict) or set(incoming['models']) != {'fast', 'smart'}:
            raise ValueError('Các chế độ model không hợp lệ')
        for key, label in (('fast', 'Nhanh'), ('smart', 'Thông minh')):
            row = incoming['models'].get(key, result['models'][key])
            if not isinstance(row, dict) or row.get('provider') not in ('gemini', 'compatible'):
                raise ValueError('Nguồn model không hợp lệ')
            model = row.get('model', '')
            if key == 'smart' and (model != ARGON or row['provider'] != 'gemini'):
                raise ValueError('Thông minh cố định dùng gemini-4-argon và pool tài khoản Gemini')
            if is_argon(str(model)) and (model != ARGON or row['provider'] != 'gemini'):
                raise ValueError('4 Argon chỉ dùng đúng route Gemini đã xác minh')
            if not isinstance(model, str) or not re.fullmatch(r'[a-zA-Z0-9_./:@+=-]{1,150}', model):
                raise ValueError('Tên model không hợp lệ')
            api_key = row.get('api_key')
            if api_key is None or api_key == '':
                api_key = result['models'][key].get('api_key', '')
            if row.get('clear_api_key') is True:
                api_key = ''
            if not isinstance(api_key, str) or len(api_key) > 2048 or any(c in api_key for c in '\r\n'):
                raise ValueError('Khóa API không hợp lệ')
            url = endpoint(row.get('url', '')) if row['provider'] == 'compatible' else ''
            result['models'][key] = {'label': label, 'provider': row['provider'], 'model': model,
                                     'url': url, 'api_key': api_key}
        embedding = incoming['embedding']
        if not isinstance(embedding, dict) or not isinstance(embedding.get('model'), str) or not re.fullmatch(r'[a-zA-Z0-9_./:@+-]{1,150}', embedding['model']):
            raise ValueError('Model embedding không hợp lệ')
        result['embedding'] = {'url': endpoint(embedding.get('url')), 'model': embedding['model']}
        path = config.get('AI_SETTINGS_FILE')
        if not path:
            raise ValueError('Chưa cấu hình kho cài đặt AI')
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp = tempfile.mkstemp(dir=destination.parent, prefix='.settings-')
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(result, stream, ensure_ascii=False)
            os.replace(temp, destination)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return public(result)


def supported_efforts(row):
    # Gemini Web's legacy Flash route reports Low for every supplied level.
    # Only Argon has been verified with upstream applied_level=1/4/2.
    return ['auto', 'low'] if row['provider'] == 'gemini' and not is_argon(row['model']) and row['model'] != FLASH else ['auto', 'low', 'medium', 'high']


def model_config(config, mode='fast'):
    if mode not in ('fast', 'smart'):
        raise PredictionError('INVALID_MODEL_MODE', 'Chọn chế độ Nhanh hoặc Thông minh', 400)
    settings = load(config)
    row = settings['models'][mode]
    result = dict(config)
    result.update(ASSISTANT_MODEL=row['model'], ASSISTANT_PROVIDER=row['provider'],
                  ASSISTANT_API_KEY=row.get('api_key', ''), ASSISTANT_RETRIEVAL_MODE='ragwire',
                  ASSISTANT_EMBEDDING_URL=settings['embedding']['url'],
                  ASSISTANT_EMBEDDING_MODEL=settings['embedding']['model'],
                  ASSISTANT_SUPPORTED_EFFORTS=supported_efforts(row))
    if row['provider'] == 'compatible':
        result['ASSISTANT_URL'] = row['url']
    return result
