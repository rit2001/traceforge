#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_command kubectl
require_command rg
rendered=$(mktemp "${TMPDIR:-/tmp}/traceforge-terraform-overlay.XXXXXX")
trap 'rm -f "$rendered"' EXIT HUP INT TERM
kubectl kustomize "$TERRAFORM_KUSTOMIZE_OVERLAY" >"$rendered"
if rg -n '^kind: (Namespace|ResourceQuota|LimitRange|ServiceAccount)$' "$rendered"; then
    echo "Terraform-backed overlay contains a Terraform-owned resource kind" >&2
    exit 1
fi
echo "Terraform/Kustomize object ownership sets are disjoint"
