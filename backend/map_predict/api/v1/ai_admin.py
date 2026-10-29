"""Password authentication is enforced here in the private AI service."""
from collections import deque
import hashlib
import hmac
import json
import math
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler

from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import check_password_hash

from ...services import ai_settings
from ...services.knowledge import json_request, retrieve
from ...services.prediction import PredictionError

admin_api = Blueprint('ai_admin', __name__, url_prefix='/api/v1/ai-admin')
COOKIE = 'map_ai_admin'
TTL = 8 * 60 * 60
FAILURES = deque(maxlen=20)
AUTH_LOCK = threading.Lock()
TOOL_LOCK = threading.BoundedSemaphore(1)
REVOKED = {}


def credentials():
    path = current_app.config.get('AI_ADMIN_PASSWORD_FILE')
    if not path or not Path(path).is_file():
        raise PredictionError('ADMIN_NOT_CONFIGURED', 'Chưa thiết lập mật khẩu quản trị trên service', 503)
    stored = Path(path).read_text(encoding='utf-8').strip()
    if not stored.startswith(('scrypt:', 'pbkdf2:')):
        raise PredictionError('ADMIN_NOT_CONFIGURED', 'Chưa thiết lập mật khẩu quản trị trên service', 503)
    return stored


def signer():
    key = Path(current_app.config['ASSISTANT_SECRET_FILE']).read_text().strip()
    return URLSafeTimedSerializer(key, salt='ai-admin-v1')


@admin_api.before_request
def protect():
    request.max_content_length = 80 * 1024
    if current_app.config.get('ASSISTANT_ROLE') != 'worker':
        if request.method != 'GET':
            origin = request.headers.get('Origin')
            if request.headers.get('Sec-Fetch-Site') == 'cross-site' or (origin and (urlsplit(origin).netloc != request.host or urlsplit(origin).scheme != request.scheme)):
                raise PredictionError('ORIGIN_NOT_ALLOWED', 'Gửi yêu cầu từ cùng website', 403)
        if not current_app.config.get('ASSISTANT_SERVICE_URL'):
            raise PredictionError('AI_SERVICE_REQUIRED', 'Trang quản trị cần service AI riêng', 503)
        from ...services.assistant_gateway import forward
        return forward(request.path.removeprefix('/api/v1/ai-admin/'), admin=True)
    # Internal Bearer authentication has already run in ai_app.py.
    if request.endpoint == 'ai_admin.login':
        return
    try:
        session = signer().loads(request.cookies.get(COOKIE, ''), max_age=TTL)
        generation = hashlib.sha256(credentials().encode()).hexdigest()
        with AUTH_LOCK:
            now = time.time()
            for key in list(REVOKED):
                if REVOKED[key] < now:
                    del REVOKED[key]
            if session['id'] in REVOKED:
                raise ValueError()
        if not hmac.compare_digest(session['generation'], generation):
            raise ValueError()
        if request.method != 'GET' and not hmac.compare_digest(request.headers.get('X-Admin-CSRF', ''), session['csrf']):
            raise PredictionError('INVALID_CSRF', 'Phiên quản trị không hợp lệ, hãy đăng nhập lại', 403)
        g.admin_session = session
    except PredictionError:
        raise
    except (BadSignature, SignatureExpired, ValueError, KeyError, TypeError):
        raise PredictionError('ADMIN_LOGIN_REQUIRED', 'Đăng nhập để quản trị AI', 401) from None


@admin_api.errorhandler(PredictionError)
def fail(error):
    return jsonify(error={'code': error.code, 'message': str(error)}), error.status


@admin_api.after_request
def private(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@admin_api.post('/login')
def login():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        raise PredictionError('INVALID_PASSWORD', 'Mật khẩu không hợp lệ', 400)
    password = body.get('password')
    if not isinstance(password, str) or not 1 <= len(password) <= 256:
        raise PredictionError('INVALID_PASSWORD', 'Mật khẩu không hợp lệ', 400)
    stored = credentials()
    with AUTH_LOCK:
        now = time.monotonic()
        while FAILURES and FAILURES[0] < now - 60:
            FAILURES.popleft()
        if len(FAILURES) >= 5:
            raise PredictionError('LOGIN_RATE_LIMIT', 'Đợi một phút trước khi đăng nhập lại', 429)
        # Count before checking the hash, including parallel requests.
        FAILURES.append(now)
    if not check_password_hash(stored, password):
        raise PredictionError('INVALID_PASSWORD', 'Mật khẩu không đúng', 401)
    session = {'id': secrets.token_hex(24), 'csrf': secrets.token_hex(24),
               'generation': hashlib.sha256(stored.encode()).hexdigest()}
    response = jsonify(data={'csrf': session['csrf']})
    response.set_cookie(COOKIE, signer().dumps(session), max_age=TTL, httponly=True,
                        secure=request.headers.get('X-Admin-Secure') == '1', samesite='Strict',
                        path='/api/v1/ai-admin')
    return response


@admin_api.post('/logout')
def logout():
    with AUTH_LOCK:
        if len(REVOKED) > 10000:
            raise PredictionError('ADMIN_BUSY', 'Thử lại sau', 429)
        REVOKED[g.admin_session['id']] = time.time() + TTL
    response = jsonify(data={'logged_out': True})
    response.delete_cookie(COOKIE, path='/api/v1/ai-admin', samesite='Strict')
    return response


def gemini_request(action='', body=None, accounts=False):
    base = current_app.config['ASSISTANT_URL'].removesuffix('/').removesuffix('/v1')
    key = Path(current_app.config['ASSISTANT_SECRET_FILE']).read_text().strip()
    payload = json.dumps(body).encode() if body is not None else None
    with build_opener(ProxyHandler({})).open(Request(base + ('/_internal/accounts' if accounts else '/_internal/session') + action,
            data=payload, headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}), timeout=150 if accounts and body is not None else 60) as response:
        return json.loads(response.read(65536))


@admin_api.get('/state')
def state():
    try:
        session = gemini_request()
    except Exception:
        session = {'state': 'unavailable'}
    try:
        accounts = gemini_request(accounts=True)
    except Exception:
        accounts = {'accounts': [], 'unavailable': True}
    return jsonify(data={'csrf': g.admin_session['csrf'], 'settings': ai_settings.public(ai_settings.load(current_app.config)),
                         'gemini': session, 'account_pool': accounts, 'pro_access': {'configured': ai_settings.has_passcode(current_app.config)}, 'chatbot_retrieval': 'qdrant_keyword',
                         'embedding_enabled': current_app.config.get('ASSISTANT_EMBEDDING_ENABLED', False),
                         'services': ['web-portal', 'ai-assistant', 'gemini-session', 'qdrant', 'web-gateway', 'cloudflare-tunnel']
                         + (['ai-embedding'] if current_app.config.get('ASSISTANT_EMBEDDING_ENABLED') else [])})


@admin_api.post('/settings')
def settings():
    try:
        return jsonify(data=ai_settings.save(current_app.config, request.get_json(silent=True)))
    except ValueError as error:
        raise PredictionError('INVALID_SETTINGS', str(error), 400) from None


@admin_api.post('/tools/<action>')
def tools(action):
    if action not in ('model-test', 'embedding-test', 'retrieval-test', 'session-import', 'session-refresh', 'accounts-import', 'accounts-scan', 'accounts-refresh', 'pro-passcode'):
        raise PredictionError('UNKNOWN_ACTION', 'Thao tác không hợp lệ', 404)
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        raise PredictionError('INVALID_INPUT', 'Nội dung không hợp lệ', 400)
    if not TOOL_LOCK.acquire(blocking=False):
        raise PredictionError('ADMIN_BUSY', 'Đang xử lý công cụ khác', 429)
    try:
        if action == 'pro-passcode':
            try:
                result = ai_settings.set_passcode(current_app.config, body.get('passcode'), disable=body.get('disable') is True)
            except ValueError as error:
                raise PredictionError('INVALID_PASSCODE', str(error), 400) from None
        elif action.startswith('accounts-'):
            result = gemini_request({'accounts-import': '/import', 'accounts-scan': '/scan', 'accounts-refresh': '/refresh'}[action], body, accounts=True)
        elif action.startswith('session-'):
            result = gemini_request('/import' if action == 'session-import' else '/refresh', body)
        elif action == 'model-test':
            from ...services.assistant import call_model
            config = ai_settings.model_config(current_app.config, body.get('mode', 'fast'))
            result = call_model([{'role': 'user', 'content': 'Trả JSON {"answer":"Kết nối thành công","sources":[],"edits":[],"scores":[]}'}], config)
            result = {'answer': result['answer'][:2000]}
        else:
            text = body.get('text', '')
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
                raise PredictionError('INVALID_INPUT', 'Nhập nội dung từ 1 đến 2000 ký tự', 400)
            embedding = ai_settings.load(current_app.config)['embedding']
            if action == 'embedding-test':
                if not current_app.config.get('ASSISTANT_EMBEDDING_ENABLED'):
                    raise PredictionError('EMBEDDING_DISABLED', 'Embedding đã tắt trong triển khai này, chatbot tra cứu trực tiếp Qdrant', 503)
                reply = json_request(embedding['url'] + '/api/embed', {'model': embedding['model'],
                                     'input': text, 'keep_alive': '0s', 'options': {'num_ctx': 2048}}, timeout=120)
                vector = reply['embeddings'][0]
                if not isinstance(vector, list) or not vector or any(type(value) not in (int, float) or not math.isfinite(value) for value in vector):
                    raise ValueError('Invalid embedding')
                result = {'dimensions': len(vector), 'model': embedding['model'], 'unload_requested': True}
            else:
                config = dict(current_app.config, ASSISTANT_RETRIEVAL_MODE='keyword')
                result = retrieve(text, config)
        return jsonify(data=result)
    except PredictionError:
        raise
    except Exception:
        raise PredictionError('ADMIN_TOOL_FAILED', 'Chưa thực hiện được, kiểm tra cấu hình và trạng thái service', 503) from None
    finally:
        TOOL_LOCK.release()
