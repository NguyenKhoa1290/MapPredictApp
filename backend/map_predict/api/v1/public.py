from flask import Blueprint, current_app, g, jsonify, request

from ...services.catalog import read_content, read_projects

public_api = Blueprint("public_api_v1", __name__, url_prefix="/api/v1")


def success(data):
    response = jsonify(data=data, meta={"schema": 1, "request_id": g.request_id})
    response.headers["Cache-Control"] = "no-cache"
    return response


@public_api.get("/health")
def health():
    return success({"status": "ok", "api_version": "v1"})


@public_api.get("/site-content")
def site_content():
    content = read_content(current_app.config["PUBLIC_CONTENT_FILE"])
    content["legacy_available"] = current_app.config["LEGACY_ENABLED"]
    return success(content)


@public_api.get("/projects")
def projects():
    return success(read_projects(current_app.config["PROJECT_CATALOG_FILE"]))


def find_project(slug):
    return next((project for project in read_projects(current_app.config["PROJECT_CATALOG_FILE"])
                 if project["id"] == slug), None)


@public_api.get("/projects/<slug>")
def project_detail(slug):
    project = find_project(slug)
    if project is None:
        return jsonify(error={"code": "PROJECT_NOT_FOUND", "message": "Không tìm thấy dự án."}, request_id=g.request_id), 404
    return success({**project, "legend": [
        {"Y": 0, "color": "#ff0000", "label": "Kết quả Y = 0"},
        {"Y": 1, "color": "#ffa500", "label": "Kết quả Y = 1"},
        {"Y": 2, "color": "#008000", "label": "Kết quả Y = 2"},
    ]})


@public_api.get("/projects/<slug>/map")
def project_map(slug):
    project = find_project(slug)
    if project is None or project["kind"] != "map":
        return jsonify(error={"code": "PROJECT_NOT_FOUND", "message": "Không tìm thấy dự án."}, request_id=g.request_id), 404
    from ...services.project_maps import project_map as load_map
    try:
        source_crs = request.args.get("source_crs", "EPSG:9208")
        return success(load_map(current_app.config["PROJECT_SOURCE_FOLDER"], slug, source_crs or None))
    except FileNotFoundError:
        return jsonify(error={"code": "PROJECT_NOT_READY", "message": "Chưa có bộ dữ liệu dự án trên máy chủ."}, request_id=g.request_id), 409
    except ValueError as error:
        return jsonify(error={"code": "INVALID_PROJECT_MAP", "message": str(error)}, request_id=g.request_id), 422
