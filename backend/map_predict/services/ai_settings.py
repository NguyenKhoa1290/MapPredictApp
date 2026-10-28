"""Persistent AI configuration, private to the authenticated AI service."""
import copy
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from urllib.parse import urlsplit

from .prediction import PredictionError

LOCK = threading.RLock()


def defaults(config):
    return {'models': {
        'fast': {'label': 'Nhanh', 'provider': 'gemini', 'model': config['ASSISTANT_MODEL'],
                 'url': '', 'api_key': ''},
        'smart': {'label': 'Thông minh', 'provider': 'gemini', 'model': 'gemini-3.5-flash-thinking',
                  'url': '', 'api_key': ''}},
        'embedding': {'url': config.get('ASSISTANT_EMBEDDING_URL') or 'http://ai-embedding:11434',
                      'model': config['ASSISTANT_EMBEDDING_MODEL']}}


def load(config):
    result = defaults(config)
    path = config.get('AI_SETTINGS_FILE')
    with LOCK:
        if path and Path(path).is_file():
            result.update(json.loads(Path(path).read_text(encoding='utf-8')))
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
            raise ValueError('Cần hai chế độ Nhanh và Thông minh')
        for key, label in (('fast', 'Nhanh'), ('smart', 'Thông minh')):
            row = incoming['models'][key]
            if not isinstance(row, dict) or row.get('provider') not in ('gemini', 'compatible'):
                raise ValueError('Nguồn model không hợp lệ')
            model = row.get('model', '')
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


def model_config(config, mode='fast'):
    if mode not in ('fast', 'smart'):
        raise PredictionError('INVALID_MODEL_MODE', 'Chọn chế độ Nhanh hoặc Thông minh', 400)
    row = load(config)['models'][mode]
    result = dict(config)
    result.update(ASSISTANT_MODEL=row['model'], ASSISTANT_PROVIDER=row['provider'],
                  ASSISTANT_API_KEY=row.get('api_key', ''), ASSISTANT_RETRIEVAL_MODE='keyword')
    if row['provider'] == 'compatible':
        result['ASSISTANT_URL'] = row['url']
    return result
