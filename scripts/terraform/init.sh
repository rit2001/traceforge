#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_command terraform
terraform -chdir="$TERRAFORM_DIRECTORY" init
