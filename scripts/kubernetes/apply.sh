#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_command kubectl
require_cluster
"$SCRIPT_DIRECTORY/validate.sh"
kubectl --context "$KUBE_CONTEXT" apply --dry-run=server \
    -f "$REPOSITORY_ROOT/deploy/kubernetes/base/namespace.yaml" >/dev/null
kubectl --context "$KUBE_CONTEXT" apply \
    -f "$REPOSITORY_ROOT/deploy/kubernetes/base/namespace.yaml" >/dev/null
kubectl --context "$KUBE_CONTEXT" apply --dry-run=server -k "$KUSTOMIZE_OVERLAY" >/dev/null
kubectl --context "$KUBE_CONTEXT" apply -k "$KUSTOMIZE_OVERLAY"
