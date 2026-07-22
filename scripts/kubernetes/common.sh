#!/bin/sh

set -eu

CLUSTER_NAME=traceforge
KUBE_CONTEXT=kind-traceforge
KUBE_NAMESPACE=traceforge
SCRIPT_DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIRECTORY/../.." && pwd)
KIND_CONFIG="$REPOSITORY_ROOT/deploy/kubernetes/overlays/kind/cluster.yaml"
KUSTOMIZE_OVERLAY="$REPOSITORY_ROOT/deploy/kubernetes/overlays/kind"

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "required command not found: $1" >&2
        exit 1
    fi
}

cluster_exists() {
    kind get clusters 2>/dev/null | grep -F -x -q "$CLUSTER_NAME"
}

require_cluster() {
    require_command kind
    if ! cluster_exists; then
        echo "kind cluster '$CLUSTER_NAME' does not exist" >&2
        exit 1
    fi
}
