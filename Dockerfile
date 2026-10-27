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

FROM python:3.11-slim-bookworm AS runtime
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
COPY app.py gis.py cad_diagnostics.py cad_to_geojson.py dwg_to_dxf.py prediction_grid.py result_join.py predict_pkl.py ./
COPY backend/ ./backend/
COPY config/ ./config/
COPY templates/ ./templates/
COPY wwwroot/ ./wwwroot/
COPY tools/audit_reference_excel.py tools/audit_reference_dxf.py ./tools/
COPY --from=frontend /build/frontend/dist/ ./frontend/dist/
RUN mkdir -p /app/models /app/project-data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --start-interval=3s --retries=4 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "2", "--timeout", "180", "--graceful-timeout", "30", "--worker-tmp-dir", "/dev/shm", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
