#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_command docker
require_command kind

if cluster_exists; then
    echo "kind cluster '$CLUSTER_NAME' already exists"
    exit 0
fi

docker info >/dev/null
kind create cluster --name "$CLUSTER_NAME" --config "$KIND_CONFIG" --wait 180s
kubectl --context "$KUBE_CONTEXT" cluster-info >/dev/null
echo "created dedicated kind cluster '$CLUSTER_NAME'"
