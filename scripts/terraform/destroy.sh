#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_command terraform
require_expected_context
if [ "${CONFIRM_TERRAFORM_DESTROY:-}" != "$EXPECTED_NAMESPACE" ]; then
    echo "set CONFIRM_TERRAFORM_DESTROY=$EXPECTED_NAMESPACE to destroy the foundation" >&2
    exit 1
fi
if check_foundation_state; then
    :
else
    state_status=$?
    if [ "$state_status" = "10" ]; then
        echo "Terraform state is empty; nothing to destroy"
        exit 0
    fi
    exit "$state_status"
fi
require_foundation_state_namespace
terraform -chdir="$TERRAFORM_DIRECTORY" destroy -auto-approve
