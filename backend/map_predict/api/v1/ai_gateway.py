"""Public web entry points forwarding to the private AI service."""
from collections import defaultdict, deque
import threading
import time
from urllib.parse import urlsplit

from flask import Blueprint, current_app, g, jsonify, request

from ...services import assistant_gateway
from shared.tabular import PredictionError

ai_gateway = Blueprint('ai_gateway', __name__)
RATES = defaultdict(deque)
RATE_LOCK = threading.Lock()


@ai_gateway.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@ai_gateway.errorhandler(PredictionError)
def failed(error):
    return jsonify(error={'code': error.code, 'message': str(error)}, request_id=g.request_id), error.status


@ai_gateway.before_request
def protect():
    admin = request.path.startswith('/api/v1/ai-admin/')
    request.max_content_length = 80 * 1024 if admin else 20 * 1024 * 1024
    if request.method != 'POST':
        return
    origin = request.headers.get('Origin')
    if request.headers.get('Sec-Fetch-Site') == 'cross-site' or (origin and (
            urlsplit(origin).netloc != request.host or urlsplit(origin).scheme != request.scheme)):
        raise PredictionError('ORIGIN_NOT_ALLOWED', 'Gửi yêu cầu từ cùng website', 403)
    if admin:
        return
    if not current_app.config['ASSISTANT_ENABLED']:
        raise PredictionError('ASSISTANT_DISABLED', 'Chatbot chưa được bật trên máy chủ', 503)
    with RATE_LOCK:
        now = time.monotonic()
        if len(RATES) > 2048:
            RATES.clear()
        visits = RATES[request.remote_addr]
        while visits and visits[0] < now - 60:
            visits.popleft()
        if len(visits) >= 6:
            raise PredictionError('RATE_LIMITED', 'Đã đạt giới hạn 6 yêu cầu mỗi phút, hãy chờ một chút', 429)
        visits.append(now)


@ai_gateway.get('/api/v1/assistant/status')
def status():
    if not current_app.config['ASSISTANT_ENABLED']:
        return jsonify(data={'enabled': False, 'modes': []})
    return assistant_gateway.forward('status')


@ai_gateway.post('/api/v1/assistant/<action>')
def assistant(action):
    if action not in ('preview', 'apply', 'export', 'authorize'):
        raise PredictionError('UNKNOWN_ACTION', 'Thao tác chưa được hỗ trợ', 404)
    return assistant_gateway.forward(action)


@ai_gateway.get('/api/v1/ai-admin/state')
def admin_state():
    return assistant_gateway.forward('state', admin=True)


@ai_gateway.post('/api/v1/ai-admin/<path:action>')
def admin_action(action):
    if action not in ('login', 'logout', 'settings') and not (
            action.startswith('tools/') and '/' not in action.removeprefix('tools/')):
        raise PredictionError('UNKNOWN_ACTION', 'Thao tác chưa được hỗ trợ', 404)
    return assistant_gateway.forward(action, admin=True)
