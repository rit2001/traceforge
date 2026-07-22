#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_command kubectl
rendered=$(mktemp "${TMPDIR:-/tmp}/traceforge-kustomize.XXXXXX")
trap 'rm -f "$rendered"' EXIT HUP INT TERM

kubectl kustomize "$KUSTOMIZE_OVERLAY" >"$rendered"
if [ ! -s "$rendered" ]; then
    echo "Kustomize produced no resources" >&2
    exit 1
fi
echo "Kustomize render passed"
