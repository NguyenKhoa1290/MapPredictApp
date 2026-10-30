"""WSGI entry point for the standalone AI/DXF service."""
import hmac
import logging
from pathlib import Path
from uuid import uuid4

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException

from backend.map_predict.config import Config


def create_ai_app(config=None):
    application = Flask(__name__)
    application.config.from_object(Config)
    application.config.update(ASSISTANT_ENABLED=True, ASSISTANT_ROLE='worker', ASSISTANT_SERVICE_URL='')
    application.logger.setLevel(logging.INFO)
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
        from backend.map_predict.services.assistant_files import prune
        from backend.map_predict.services.assistant_dxf import prune as prune_summaries
        try:
            prune(application.config)
            prune_summaries()
        except OSError:
            pass
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
    from backend.map_predict.api.v1.ai_admin import admin_api
    application.register_blueprint(admin_api)
    return application


app = create_ai_app()
