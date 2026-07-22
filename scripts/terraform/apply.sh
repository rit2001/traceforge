#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_command terraform
require_expected_context
plan="$TERRAFORM_DIRECTORY/traceforge.tfplan"
if [ ! -f "$plan" ]; then
    echo "saved plan not found: run make terraform-plan first" >&2
    exit 1
fi
terraform -chdir="$TERRAFORM_DIRECTORY" apply traceforge.tfplan
