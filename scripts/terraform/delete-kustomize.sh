#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_expected_context
require_foundation_state
if [ "${CONFIRM_APPLICATION_DELETE:-}" != "$EXPECTED_NAMESPACE" ]; then
    echo "set CONFIRM_APPLICATION_DELETE=$EXPECTED_NAMESPACE to delete application resources" >&2
    exit 1
fi
kubectl --context "$EXPECTED_CONTEXT" delete -k "$TERRAFORM_KUSTOMIZE_OVERLAY" \
    --ignore-not-found=true
