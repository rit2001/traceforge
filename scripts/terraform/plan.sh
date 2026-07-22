#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_command terraform
require_expected_context
terraform -chdir="$TERRAFORM_DIRECTORY" plan -out=traceforge.tfplan
