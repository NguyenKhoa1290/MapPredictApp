from pathlib import Path

from flask import Blueprint, abort, current_app, g, jsonify, redirect, send_from_directory

frontend = Blueprint("frontend", __name__)


@frontend.get("/portal")
def portal_redirect():
    return redirect("/portal/")


@frontend.get("/portal/assets/<path:filename>")
def frontend_asset(filename):
    response = send_from_directory(Path(current_app.config["FRONTEND_DIST"]) / "assets", filename)
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


@frontend.get("/portal/")
@frontend.get("/portal/<path:route>")
def frontend_page(route=""):
    valid_routes = {"", "projects", "assessment", "assessment/csv", "projects/hcm", "projects/bac-kan", "projects/phu-quoc"}
    if route.rstrip("/") not in valid_routes:
        abort(404)
    directory = Path(current_app.config["FRONTEND_DIST"])
    if not (directory / "index.html").is_file():
        return jsonify(error={"code": "FRONTEND_NOT_BUILT", "message": "Cần chạy npm ci và npm run build trong frontend."}, request_id=g.request_id), 503
    response = send_from_directory(directory, "index.html")
    response.headers["Cache-Control"] = "no-store"
    return response
