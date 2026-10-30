"""Anonymous, bounded assistant API, all uploads remain request-scoped."""
from collections import defaultdict, deque
import base64
import io
import json
from pathlib import Path
import tempfile
import threading
import time
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, request, g, send_file

from ...services import assistant
from ...services import assistant_files
from ...services.prediction import PredictionError

assistant_api = Blueprint('assistant_v1', __name__, url_prefix='/api/v1/assistant')
BUSY = threading.BoundedSemaphore(1)
RATE_LOCK = threading.Lock()
RATES = defaultdict(deque)


@assistant_api.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@assistant_api.errorhandler(PredictionError)
def failed(error):
    return jsonify(error={'code': error.code, 'message': str(error)}, request_id=g.request_id), error.status


@assistant_api.before_request
def limits():
    request.max_content_length = 20 * 1024 * 1024
    if request.method != 'POST':
        return
    if not current_app.config['ASSISTANT_ENABLED']:
        raise PredictionError('ASSISTANT_DISABLED', 'Chatbot chưa được bật trên máy chủ', 503)
    if current_app.config.get('ASSISTANT_ROLE') == 'worker':
        return
    origin = request.headers.get('Origin')
    if request.headers.get('Sec-Fetch-Site') == 'cross-site' or (origin and urlsplit(origin).netloc != request.host):
        raise PredictionError('ORIGIN_NOT_ALLOWED', 'Gửi yêu cầu từ cùng website', 403)
    if origin and urlsplit(origin).scheme != request.scheme:
        raise PredictionError('ORIGIN_NOT_ALLOWED', 'Gửi yêu cầu từ cùng website', 403)
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


@assistant_api.get('/status')
def status():
    if current_app.config['ASSISTANT_ENABLED'] and current_app.config.get('ASSISTANT_SERVICE_URL'):
        from ...services.assistant_gateway import forward
        return forward('status')
    from ...services.ai_settings import load, is_argon, argon_availability, COOKIE_MESSAGE, supported_efforts
    modes = load(current_app.config)['models']
    availability = argon_availability(current_app.config) if current_app.config['ASSISTANT_ENABLED'] else 'unknown'
    return jsonify(data={'enabled': current_app.config['ASSISTANT_ENABLED'],
                         'modes': [{'id': key, 'label': modes[key]['label'], 'requires_passcode': is_argon(modes[key]['model']),
                                    'efforts': supported_efforts(modes[key]),
                                    'availability': availability if is_argon(modes[key]['model']) else 'ready',
                                    'message': COOKIE_MESSAGE if availability == 'cookie_required' and is_argon(modes[key]['model']) else ''}
                                   for key in ('fast', 'smart')],
                         'retrieval': 'qdrant_keyword',
                         'model': current_app.config['ASSISTANT_MODEL'], 'apply': 'preview_required',
                         'service': current_app.config.get('ASSISTANT_ROLE', 'web'),
                         'collection': current_app.config.get('ASSISTANT_QDRANT_COLLECTION')
                         if current_app.config.get('ASSISTANT_QDRANT_URL') else None})


def uploaded(name, extension, limit):
    files = request.files.getlist(name)
    if not files:
        return b''
    if len(files) != 1 or Path(files[0].filename or '').suffix.lower() != extension:
        raise PredictionError('INVALID_ATTACHMENT', f'Chỉ nhận một file {extension} cho {name}', 400)
    content = files[0].read(limit + 1)
    if not content or len(content) > limit:
        raise PredictionError('ATTACHMENT_TOO_LARGE', f'File {name} rỗng hoặc vượt giới hạn dung lượng', 413)
    return content


@assistant_api.post('/<action>')
def execute(action):
    if action not in ('preview', 'apply', 'export', 'authorize'):
        raise PredictionError('UNKNOWN_ACTION', 'Thao tác chưa được hỗ trợ', 404)
    if current_app.config.get('ASSISTANT_SERVICE_URL'):
        from ...services.assistant_gateway import forward
        return forward(action)
    if action == 'authorize':
        from ...services.ai_settings import model_config, authorize_pro
        config = model_config(current_app.config, 'smart')
        authorize_pro(config, request.form.get('passcode', ''))
        return jsonify(data={'authorized': True})
    if set(request.files) - {'dxf', 'csv'}:
        raise PredictionError('INVALID_ATTACHMENT', 'Chỉ gửi DXF và CSV đã chọn', 400)
    options = request.form.to_dict()
    scope = options.get('scope', 'legacy')
    if scope not in ('legacy', 'map', 'prediction'):
        raise PredictionError('INVALID_CONTEXT', 'Tab dữ liệu không hợp lệ', 400)
    resources = []
    if scope == 'map':
        files = request.files.getlist('dxf')
        try:
            if len(options.get('resource_ids', '[]')) > 4096 or len(options.get('resource_tokens', '')) > 24576:
                raise ValueError()
            ids = json.loads(options.get('resource_ids', '[]'))
            if not isinstance(ids, list) or not (0 if action == 'preview' else 1) <= len(ids) <= 5:
                raise ValueError()
            refs = json.loads(options['resource_tokens']) if 'resource_tokens' in options else [None] * len(ids)
            if (not isinstance(refs, list) or len(refs) != len(ids) or len(set(ids)) != len(ids)
                    or len(files) != sum(ref is None for ref in refs)):
                raise ValueError()
            uploads = iter(files)
            for source_id, ref in zip(ids, refs):
                if not isinstance(source_id, str) or not 1 <= len(source_id) <= 100:
                    raise ValueError()
                if ref is not None:
                    if not isinstance(ref, str) or len(ref) > 4096:
                        raise ValueError()
                    resources.append(assistant_files.resolve(ref, source_id, current_app.config))
                    continue
                item = next(uploads)
                if Path(item.filename or '').suffix.lower() != '.dxf':
                    raise ValueError()
                content = item.read(assistant.MAX_FILE + 1)
                if not content or len(content) > assistant.MAX_FILE:
                    raise ValueError()
                resources.append({'id': source_id, 'name': Path(item.filename).name, 'data': content})
        except PredictionError:
            raise
        except (ValueError, TypeError):
            raise PredictionError('MAP_RESOURCE_REQUIRED', 'Cần từ 1 đến 5 DXF đã nạp và bật trên bản đồ, tối đa 12 MB mỗi file', 400) from None
        if request.files.getlist('csv'):
            raise PredictionError('INVALID_CONTEXT', 'Tab bản đồ chỉ dùng DXF đang hiển thị', 400)
        dxf = assistant.resource_bytes(resources)
        csv = b''
    else:
        dxf = uploaded('dxf', '.dxf', assistant.MAX_FILE)
        csv = uploaded('csv', '.csv', 5 * 1024 * 1024)
        if scope == 'prediction' and dxf:
            raise PredictionError('INVALID_CONTEXT', 'Tab dự đoán chỉ dùng bảng CSV', 400)
    if action == 'preview':
        if not 1 <= len(options.get('message', '').strip()) <= 4000:
            raise PredictionError('MESSAGE_REQUIRED', 'Nhập yêu cầu từ 1 đến 4000 ký tự', 400)
        try:
            options['start'] = max(1, min(10000, int(options.get('start', '1'))))
            options['history'] = json.loads(options.get('history', '[]'))
            if not isinstance(options['history'], list) or len(options['history']) > 20:
                raise ValueError()
        except (ValueError, TypeError):
            raise PredictionError('INVALID_CONTEXT', 'Phạm vi dòng hoặc hội thoại không hợp lệ', 400)
        if len(options.get('layer', '')) > 100 or len(options.get('history', [])) > 20:
            raise PredictionError('INVALID_CONTEXT', 'Ngữ cảnh vượt giới hạn', 400)
    if not BUSY.acquire(blocking=False):
        raise PredictionError('ASSISTANT_BUSY', 'Chatbot đang xử lý một yêu cầu, hãy thử lại sau', 429)
    try:
        with tempfile.TemporaryDirectory(prefix='map-assistant-') as folder:
            path = Path(folder) / 'drawing.dxf'
            if resources:
                for index, resource in enumerate(resources):
                    resource['path'] = Path(folder) / f'drawing-{index}.dxf'
                    resource['path'].write_bytes(resource['data'])
            elif dxf:
                path.write_bytes(dxf)
            try:
                if action == 'preview':
                    result = assistant.preview(path, dxf, csv, options, current_app.config, resources=resources)
                else:
                    result = assistant.apply(path, dxf, csv, options.get('token', ''), current_app.config, resources=resources)
            except (ValueError, assistant.ezdxf.DXFError) as error:
                if isinstance(error, PredictionError):
                    raise
                raise PredictionError('INVALID_DRAWING', 'DXF hoặc đề xuất không hợp lệ, dữ liệu chưa thay đổi') from error
        if resources:
            references = []
            for resource in resources:
                try:
                    reference = resource.get('cache') or assistant_files.store(resource, current_app.config)
                    if reference:
                        references.append(reference)
                except OSError:
                    pass  # Caching is optional; a successful edit must still be returned.
            result['resource_cache'] = references
        current_app.logger.info('assistant_request %s', json.dumps({
            'request_id': g.request_id, 'action': action,
            'dxf_bytes': sum(len(resource['data']) for resource in resources) if resources else len(dxf),
            'cached_files': sum('cache' in resource for resource in resources),
            'timings': result.get('timings', {})}, separators=(',', ':')))
        if action == 'export':
            if resources:
                raise PredictionError('INVALID_CONTEXT', 'Xuất từng DXF đã duyệt trong dự án', 400)
            if not result['dxf']:
                raise PredictionError('NO_DXF_CHANGES', 'Bản xem trước chưa có thay đổi DXF để xuất', 400)
            name = Path(request.files['dxf'].filename).stem + '_edited.dxf'
            return send_file(io.BytesIO(base64.b64decode(result['dxf'])), mimetype='application/dxf',
                             as_attachment=True, download_name=name, max_age=0)
        return jsonify(data=result)
    finally:
        BUSY.release()
