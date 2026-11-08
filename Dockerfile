FROM python:3.12-alpine@sha256:e064671ca452259bab50e8e2c7bd896e39e9a343bb06ca25234adf6fe18d0fc7 AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/service
WORKDIR /service
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && addgroup -S -g 10001 app \
    && adduser -S -D -u 10001 -G app app
COPY app ./app
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]

FROM base AS test
USER root
COPY requirements-dev.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests
ENV RUFF_CACHE_DIR=/tmp/ruff-cache PYTEST_ADDOPTS="-p no:cacheprovider"
USER 10001:10001
CMD ["pytest", "-q"]
