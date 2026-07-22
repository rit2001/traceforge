#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_expected_context
require_foundation_state
kubectl --context "$EXPECTED_CONTEXT" get namespace "$EXPECTED_NAMESPACE" >/dev/null
kubectl --context "$EXPECTED_CONTEXT" apply --dry-run=server \
    -k "$TERRAFORM_KUSTOMIZE_OVERLAY" >/dev/null
kubectl --context "$EXPECTED_CONTEXT" apply -k "$TERRAFORM_KUSTOMIZE_OVERLAY"
