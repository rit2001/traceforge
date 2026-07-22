#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_command kind

if ! cluster_exists; then
    echo "kind cluster '$CLUSTER_NAME' is already absent"
    exit 0
fi

kind delete cluster --name "$CLUSTER_NAME"
if cluster_exists; then
    echo "kind cluster '$CLUSTER_NAME' still exists after delete" >&2
    exit 1
fi
echo "deleted dedicated kind cluster '$CLUSTER_NAME'"
