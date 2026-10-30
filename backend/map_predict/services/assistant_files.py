"""Short-lived, bounded DXF reuse; references are signed bearer capabilities."""
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import threading
import time

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from .prediction import PredictionError

TTL = 15 * 60
MAX_BYTES = 64 * 1024 * 1024
MAX_FILES = 16
LOCK = threading.RLock()


def root(config):
    explicit = config.get('ASSISTANT_DXF_CACHE_DIR')
    settings = config.get('AI_SETTINGS_FILE')
    return Path(explicit) if explicit else Path(settings).parent / 'dxf-cache' if settings else None


def signer(config):
    from .assistant import EPHEMERAL_KEY
    path = config.get('ASSISTANT_SECRET_FILE')
    key = Path(path).read_text().strip() if path else EPHEMERAL_KEY
    return URLSafeTimedSerializer(key, salt='assistant-dxf-resource-v1')


def prune(config, needed=0):
    folder = root(config)
    if folder is None or not folder.is_dir():
        return
    with LOCK:
        files = []
        for path in folder.glob('*.dxf'):
            if not re.fullmatch(r'[0-9a-f]{32}\.dxf', path.name):
                continue
            try:
                info = path.lstat()
                if path.is_symlink() or time.time() - info.st_mtime > TTL:
                    path.unlink()
                else:
                    files.append((info.st_mtime, path, info.st_size))
            except FileNotFoundError:
                pass
        files.sort(key=lambda item: item[0])
        total = sum(size for _, _, size in files)
        while files and (total + needed > MAX_BYTES or len(files) + bool(needed) > MAX_FILES):
            _, path, size = files.pop(0)
            path.unlink(missing_ok=True)
            total -= size


def store(resource, config):
    folder = root(config)
    if folder is None or not resource['data'] or len(resource['data']) > MAX_BYTES:
        return None
    with LOCK:
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        prune(config, len(resource['data']))
        identifier = secrets.token_hex(16)
        path = folder / (identifier + '.dxf')
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(resource['data'])
        token = signer(config).dumps({'id': identifier, 'source_id': resource['id'],
            'name': resource['name'], 'hash': hashlib.sha256(resource['data']).hexdigest()})
    return {'source_id': resource['id'], 'token': token, 'expires_in': TTL}


def resolve(token, source_id, config):
    try:
        data, issued = signer(config).loads(token, max_age=TTL, return_timestamp=True)
        if (not isinstance(data, dict) or data.get('source_id') != source_id
                or not isinstance(data.get('id'), str) or not re.fullmatch(r'[0-9a-f]{32}', data['id'])
                or not isinstance(data.get('name'), str) or not data['name'].lower().endswith('.dxf')
                or not isinstance(data.get('hash'), str) or not re.fullmatch(r'[0-9a-f]{64}', data['hash'])):
            raise BadSignature('Invalid resource reference')
    except SignatureExpired:
        raise PredictionError('ASSISTANT_RESOURCE_EXPIRED', 'Cần gửi lại DXF đã hết thời gian lưu tạm', 410) from None
    except (BadSignature, TypeError, ValueError):
        raise PredictionError('INVALID_RESOURCE_REFERENCE', 'Tham chiếu DXF không hợp lệ', 400) from None
    folder = root(config)
    try:
        if folder is None:
            raise FileNotFoundError()
        path = folder / (data['id'] + '.dxf')
        with LOCK:
            if path.is_symlink() or time.time() - path.stat().st_mtime > TTL:
                raise FileNotFoundError()
            with path.open('rb') as stream:
                content = stream.read(12 * 1024 * 1024 + 1)
        if len(content) > 12 * 1024 * 1024 or not hmac.compare_digest(hashlib.sha256(content).hexdigest(), data['hash']):
            raise FileNotFoundError()
    except (FileNotFoundError, OSError):
        raise PredictionError('ASSISTANT_RESOURCE_EXPIRED', 'Cần gửi lại DXF không còn trong bộ nhớ tạm', 410) from None
    return {'id': source_id, 'name': data['name'], 'data': content,
            'cache': {'source_id': source_id, 'token': token,
                      'expires_in': max(0, int(TTL - (time.time() - issued.timestamp())))}}
