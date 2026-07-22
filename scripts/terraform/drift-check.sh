#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_command terraform
require_expected_context
require_managed_namespace
set +e
terraform -chdir="$TERRAFORM_DIRECTORY" plan -detailed-exitcode
status=$?
set -e
case "$status" in
    0)
        echo "Terraform reports zero drift"
        ;;
    2)
        echo "Terraform detected drift" >&2
        ;;
    *)
        echo "Terraform drift check failed with exit code $status" >&2
        ;;
esac
exit "$status"
