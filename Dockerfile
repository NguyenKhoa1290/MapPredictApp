FROM node:24.21.0-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY config/ /build/config/
RUN npm run build

FROM python:3.11-slim-bookworm AS dependencies
WORKDIR /build
COPY requirements.txt requirements-production.txt ./
RUN pip install --prefix=/install --no-compile --no-cache-dir -r requirements-production.txt \
    && find /install/lib/python3.11/site-packages -type d \( -name tests -o -name test \) -prune -exec rm -rf '{}' +

FROM python:3.11-slim-bookworm AS gemini
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
WORKDIR /app
RUN pip install --no-cache-dir httpx==0.28.1
COPY integrations/gemini_web2api/ ./gemini_web2api/
COPY integrations/run_gemini.py ./run_gemini.py
COPY integrations/GEMINI_LICENSE ./GEMINI_LICENSE
RUN mkdir -p /var/lib/gemini-session && chown 10001:10001 /var/lib/gemini-session
USER 10001:10001
EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --start-interval=2s \
    CMD python -c "from pathlib import Path; from urllib.request import Request,urlopen; urlopen(Request('http://127.0.0.1:8081/v1/models',headers={'Authorization':'Bearer '+Path('/run/secrets/assistant_key').read_text().strip()}),timeout=3)"
CMD ["python", "-B", "run_gemini.py"]

FROM python:3.11-slim-bookworm AS application
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/cache \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    MAP_PREDICT_MODEL_DIR=/app/models \
    MAP_PREDICT_PROJECT_SOURCE_FOLDER=/app/project-data
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --no-create-home appuser
COPY --from=dependencies /install/ /usr/local/
COPY app.py ai_app.py gis.py cad_diagnostics.py cad_to_geojson.py dwg_to_dxf.py prediction_grid.py result_join.py predict_pkl.py ./
COPY backend/ ./backend/
COPY config/ ./config/
COPY templates/ ./templates/
COPY wwwroot/ ./wwwroot/
COPY tools/audit_reference_excel.py tools/audit_reference_dxf.py tools/auto_deploy.py tools/docker_stack.py tools/install_linux.py ./tools/
COPY --from=frontend /build/frontend/dist/ ./frontend/dist/
RUN mkdir -p /app/models /app/project-data /var/lib/map-predict-ai && chown 10001:10001 /var/lib/map-predict-ai
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --start-interval=3s --retries=4 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "2", "--timeout", "180", "--graceful-timeout", "30", "--worker-tmp-dir", "/dev/shm", "--access-logfile", "-", "--error-logfile", "-", "app:app"]

FROM application AS ai
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --start-interval=2s --retries=4 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8001/health',timeout=3)"
CMD ["gunicorn", "--bind", "0.0.0.0:8001", "--workers", "1", "--threads", "2", "--timeout", "180", "--graceful-timeout", "180", "--worker-tmp-dir", "/dev/shm", "--access-logfile", "-", "--error-logfile", "-", "ai_app:app"]

FROM application AS runtime
