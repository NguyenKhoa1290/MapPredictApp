"""Read only curated public metadata, never arbitrary paths or reference files."""
import json


PROJECT_FIELDS = ("id", "name", "region", "kind", "category", "index", "variant", "status")


def read_content(path):
    with open(path, encoding="utf-8") as source:
        content = json.load(source)
    return {key: content[key] for key in ("brand", "intro", "visions", "members", "content_status")}


def read_projects(path):
    with open(path, encoding="utf-8") as source:
        catalog = json.load(source)
    projects = [{key: project[key] for key in PROJECT_FIELDS} for project in catalog["projects"]]
    if len({project["id"] for project in projects}) != len(projects):
        raise ValueError("Duplicate project IDs in public catalog")
    return projects
