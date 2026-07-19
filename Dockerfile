FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml ./
COPY schemas ./schemas
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels ".[dashboard]"

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 traceforge
WORKDIR /app
RUN chown traceforge:traceforge /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels "traceforge-replay[dashboard]" \
    && rm -rf /wheels
USER traceforge
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
CMD ["traceforge", "serve", "--host", "0.0.0.0", "--port", "8000"]
