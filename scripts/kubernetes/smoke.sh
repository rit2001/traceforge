#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_command kubectl
require_cluster

PYTHON_EXECUTABLE=${PYTHON_EXECUTABLE:-"$REPOSITORY_ROOT/.venv/bin/python"}
if [ ! -x "$PYTHON_EXECUTABLE" ]; then
    echo "Python environment not found at $PYTHON_EXECUTABLE" >&2
    exit 1
fi

"$PYTHON_EXECUTABLE" "$REPOSITORY_ROOT/scripts/kubernetes_smoke.py" \
    --context "$KUBE_CONTEXT" --namespace "$KUBE_NAMESPACE"
