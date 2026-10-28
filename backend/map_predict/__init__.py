"""Application factory for the portal, public maps and request-scoped predictions."""
from uuid import uuid4
from urllib.parse import urlsplit

from flask import Flask, abort, g, jsonify, redirect, request
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config, ROOT


def create_app(config=None, *, legacy_blueprint=None, legacy_error_handler=None):
    application = Flask(__name__, static_folder=str(ROOT / "wwwroot"), static_url_path="/static",
                        template_folder=str(ROOT / "templates"))
    application.config.from_object(Config)
    if config:
        application.config.update(config)
    if application.config["PROXY_HOPS"]:
        application.wsgi_app = ProxyFix(application.wsgi_app,
                                       x_for=application.config["PROXY_HOPS"],
                                       x_proto=application.config["PROXY_HOPS"], x_host=0, x_port=0, x_prefix=0)
    application.config["LEGACY_ENABLED"] = legacy_blueprint is not None

    @application.before_request
    def request_identity():
        g.request_id = uuid4().hex
        hostname = urlsplit(request.host_url).hostname
        admin_path = (request.path.rstrip('/') == '/portal/admin/ai'
                      or request.path == '/api/v1/ai-admin'
                      or request.path.startswith('/api/v1/ai-admin/'))
        if admin_path and hostname not in (application.config['ADMIN_HOST'], 'localhost', '127.0.0.1', '::1'):
            abort(404)
        if (hostname == application.config['ADMIN_HOST']
                and request.path in ('/', '/portal', '/portal/')):
            return redirect('/portal/admin/ai')

    @application.after_request
    def response_identity(response):
        response.headers["X-Request-ID"] = g.request_id
        return response

    from .api.frontend import frontend
    from .api.v1.public import public_api
    from .api.v1.predictions import predictions
    application.register_blueprint(frontend)
    application.register_blueprint(public_api)
    application.register_blueprint(predictions)
    from .api.v1.assistant import assistant_api
    application.register_blueprint(assistant_api)
    from .api.v1.ai_admin import admin_api
    application.register_blueprint(admin_api)

    if legacy_blueprint is not None:
        application.register_blueprint(legacy_blueprint)
    else:
        application.add_url_rule("/", "portal_home", lambda: redirect("/portal/"))

    @application.errorhandler(Exception)
    def handle_error(error):
        if legacy_error_handler is not None and not request.path.startswith(("/api/v1/", "/portal")):
            return legacy_error_handler(error)
        if isinstance(error, HTTPException):
            return jsonify(error={"code": error.name.upper().replace(" ", "_"),
                                  "message": error.description}, request_id=g.request_id), error.code
        application.logger.exception("Unhandled request error")
        return jsonify(error={"code": "INTERNAL_ERROR", "message": "Không thể xử lý yêu cầu."},
                       request_id=g.request_id), 500

    return application
