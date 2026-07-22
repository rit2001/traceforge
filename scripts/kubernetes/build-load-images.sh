#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_command docker
require_command kind
require_cluster
docker info >/dev/null

docker build --platform linux/arm64 --file "$REPOSITORY_ROOT/Dockerfile.kafka" \
    --tag traceforge/python:0.3.0-local "$REPOSITORY_ROOT"
docker build --platform linux/arm64 --file "$REPOSITORY_ROOT/services/ingest-gateway/Dockerfile" \
    --tag traceforge/ingest-gateway:0.3.0-local "$REPOSITORY_ROOT"
kind load docker-image --name "$CLUSTER_NAME" \
    traceforge/python:0.3.0-local traceforge/ingest-gateway:0.3.0-local
echo "built and loaded ARM64 TraceForge images into '$CLUSTER_NAME'"
