"""WSGI entry point for the standalone AI/DXF service."""
import hmac
from pathlib import Path
from uuid import uuid4

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException

from backend.map_predict.config import Config


def create_ai_app(config=None):
    application = Flask(__name__)
    application.config.from_object(Config)
    application.config.update(ASSISTANT_ENABLED=True, ASSISTANT_ROLE='worker', ASSISTANT_SERVICE_URL='')
    if config:
        application.config.update(config)

    @application.before_request
    def authenticate():
        g.request_id = uuid4().hex
        if request.path == '/health' and request.method == 'GET':
            return
        key = Path(application.config['ASSISTANT_SECRET_FILE']).read_text().strip()
        if not hmac.compare_digest(request.headers.get('Authorization', ''), 'Bearer ' + key):
            return jsonify(error={'code': 'UNAUTHORIZED', 'message': 'Yêu cầu nội bộ chưa được xác thực'}), 401

    @application.get('/health')
    def health():
        return jsonify(status='ok', service='ai')

    @application.errorhandler(Exception)
    def error(error):
        if isinstance(error, HTTPException):
            return jsonify(error={'code': error.name.upper().replace(' ', '_'),
                                  'message': error.description}), error.code
        application.logger.exception('AI request failed')
        return jsonify(error={'code': 'AI_ERROR', 'message': 'Service AI không thể xử lý yêu cầu'}), 500

    from backend.map_predict.api.v1.assistant import assistant_api
    application.register_blueprint(assistant_api)
    return application


app = create_ai_app()
