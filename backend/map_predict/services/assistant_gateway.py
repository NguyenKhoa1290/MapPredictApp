"""Forward only the assistant API to a private, authenticated AI worker."""
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

from flask import Response, current_app, request
from .prediction import PredictionError


def forward(action, admin=False):
    base = current_app.config['ASSISTANT_SERVICE_URL'].rstrip('/')
    key = Path(current_app.config['ASSISTANT_SECRET_FILE']).read_text().strip()
    headers = {'Authorization': 'Bearer ' + key}
    if admin:
        headers.update({'Cookie': request.headers.get('Cookie', ''),
                        'X-Admin-CSRF': request.headers.get('X-Admin-CSRF', ''),
                        'X-Admin-Secure': '1' if request.is_secure else '0'})
    if request.content_type:
        headers['Content-Type'] = request.content_type
    data = request.get_data() if request.method == 'POST' else None
    incoming = Request(base + ('/api/v1/ai-admin/' if admin else '/api/v1/assistant/') + action, data=data,
                       headers=headers, method=request.method)
    try:
        try:
            remote = build_opener(ProxyHandler({})).open(incoming, timeout=165)
        except HTTPError as error:
            remote = error
        with remote:
            content = remote.read(36 * 1024 * 1024 + 1)
            if len(content) > 36 * 1024 * 1024:
                raise ValueError('Response too large')
            result = Response(content, status=remote.code,
                              content_type=remote.headers.get('Content-Type', 'application/json'))
            if remote.headers.get('Content-Disposition'):
                result.headers['Content-Disposition'] = remote.headers['Content-Disposition']
            if admin:
                for cookie in remote.headers.get_all('Set-Cookie', []):
                    result.headers.add('Set-Cookie', cookie)
            return result
    except Exception as error:
        raise PredictionError('AI_SERVICE_UNAVAILABLE', 'Service AI chưa trả lời, dữ liệu chưa thay đổi', 503) from error
