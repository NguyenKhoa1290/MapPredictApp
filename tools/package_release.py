"""Bundle application files without private reference data or environments."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "app.py", "ai_app.py", "gis.py", "cad_diagnostics.py", "cad_to_geojson.py", "dwg_to_dxf.py",
    "prediction_grid.py", "result_join.py", "predict_pkl.py", "requirements.txt", "run_python.bat",
    "README.md", "NHAT_KY_DU_AN.md", "NOTE_CONG_VIEC.md", "models/README.md",
    "models/rf_model_rating_pipeline.pkl", "tools/audit_reference_excel.py", "tools/audit_reference_dxf.py",
)
FOLDERS = ("backend", "config", "templates", "wwwroot", "frontend/dist", "docs")


def sources():
    paths = [ROOT / name for name in FILES]
    for folder in FOLDERS:
        directory = ROOT / folder
        if not directory.is_dir():
            raise FileNotFoundError(f"Missing bundle directory: {folder}")
        paths.extend(path for path in directory.rglob("*") if path.is_file()
                     and "__pycache__" not in path.parts and path.suffix != ".pyc")
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Missing bundle file: {path.relative_to(ROOT)}")
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise FileNotFoundError("Build frontend before packaging")
    return sorted(set(paths))


def package(destination):
    paths = sources()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(ROOT).as_posix())
    return len(paths)


def smoke_test(destination):
    script = '''
import io
from app import app
client = app.test_client()
assert client.get('/').location == '/portal/'
for route in ('/portal/', '/portal/projects', '/portal/assessment', '/legacy/?embedded=1'):
    response = client.get(route)
    assert response.status_code == 200, (route, response.status_code)
assert client.get('/api/v1/predictions/model').json['data']['ready']
response = client.post('/api/predict', data={'csv': (io.BytesIO(b'id,x1,x2,x3,x4,x5,x6,x7,x8,x9\\nA,1,2,3,4,5,6,7,8,9\\n'), 'input.csv')})
assert response.status_code == 200, response.json
assert response.json['rows'][0]['Y'] in (0, 1, 2)
assert client.get('/api/results').json['rows'] == []
for slug in ('hcm', 'bac-kan', 'phu-quoc'):
    response = client.get('/api/v1/projects/' + slug + '/map?source_crs=EPSG:9208')
    assert response.status_code == 409, (slug, response.status_code)
    assert response.json['error']['code'] == 'PROJECT_NOT_READY'
print('Extracted bundle passed, private project sources are provisioned separately')
'''
    with tempfile.TemporaryDirectory(prefix="map-predict-bundle-") as directory:
        with ZipFile(destination) as archive:
            archive.extractall(directory)
        environment = dict(os.environ)
        environment.pop("MAP_PREDICT_MODEL_DIR", None)
        subprocess.run([sys.executable, "-I", "-B", "-c", "import sys; sys.path.insert(0, '.');\n" + script],
                       cwd=directory, check=True, timeout=120, env=environment)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/MapPredictApp.zip")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    count = package(args.output)
    if args.smoke_test:
        smoke_test(args.output)
    print(json.dumps({"file_count": count, "bytes": args.output.stat().st_size,
                      "output": str(args.output)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
