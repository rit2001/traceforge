FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml ./
COPY examples ./examples
COPY schemas ./schemas
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels ".[dashboard,kafka]"

FROM python:3.12-slim AS runtime

ARG TRACEFORGE_VERSION=0.4.1
LABEL org.opencontainers.image.title="TraceForge" \
      org.opencontainers.image.description="Deterministic offline replay for failed Python agent runs" \
      org.opencontainers.image.version="$TRACEFORGE_VERSION" \
      org.opencontainers.image.licenses="Apache-2.0"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 traceforge
WORKDIR /app
RUN chown traceforge:traceforge /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels "traceforge-replay[dashboard,kafka]" \
    && rm -rf /wheels
USER traceforge
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
CMD ["traceforge", "serve", "--host", "0.0.0.0", "--port", "8000"]
