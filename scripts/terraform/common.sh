#!/bin/sh

set -eu

EXPECTED_CLUSTER=traceforge
EXPECTED_CONTEXT=kind-traceforge
EXPECTED_NAMESPACE=traceforge
TERRAFORM_SCRIPT_DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$TERRAFORM_SCRIPT_DIRECTORY/../.." && pwd)
TERRAFORM_DIRECTORY="$REPOSITORY_ROOT/infra/terraform/environments/kind"
TERRAFORM_KUSTOMIZE_OVERLAY="$REPOSITORY_ROOT/deploy/kubernetes/overlays/terraform-kind"

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "required command not found: $1" >&2
        exit 1
    fi
}

require_expected_context() {
    require_command kubectl
    require_command kind
    current_context=$(kubectl config current-context)
    if [ "$current_context" != "$EXPECTED_CONTEXT" ]; then
        echo "expected kubectl context '$EXPECTED_CONTEXT', got '$current_context'" >&2
        exit 1
    fi
    if ! kind get clusters 2>/dev/null | grep -F -x -q "$EXPECTED_CLUSTER"; then
        echo "dedicated kind cluster '$EXPECTED_CLUSTER' does not exist" >&2
        exit 1
    fi
}

require_managed_namespace() {
    if ! managed_state=$(terraform -chdir="$TERRAFORM_DIRECTORY" state list); then
        echo "failed to read Terraform state" >&2
        exit 1
    fi
    if [ -z "$managed_state" ]; then
        return 0
    fi
    if ! managed_namespace=$(terraform -chdir="$TERRAFORM_DIRECTORY" output -raw namespace_name); then
        echo "failed to read Terraform namespace output" >&2
        exit 1
    fi
    if [ "$managed_namespace" != "$EXPECTED_NAMESPACE" ]; then
        echo "Terraform state targets unexpected namespace '$managed_namespace'" >&2
        exit 1
    fi
}

foundation_resource_id() {
    case "$1" in
        'module.foundation.kubernetes_limit_range_v1.foundation')
            printf '%s\n' 'traceforge/traceforge-container-defaults'
            ;;
        'module.foundation.kubernetes_namespace_v1.traceforge')
            printf '%s\n' 'traceforge'
            ;;
        'module.foundation.kubernetes_resource_quota_v1.foundation')
            printf '%s\n' 'traceforge/traceforge-foundation'
            ;;
        'module.foundation.kubernetes_service_account_v1.workload["ingest-gateway"]')
            printf '%s\n' 'traceforge/ingest-gateway'
            ;;
        'module.foundation.kubernetes_service_account_v1.workload["kafka"]')
            printf '%s\n' 'traceforge/kafka'
            ;;
        'module.foundation.kubernetes_service_account_v1.workload["otel-collector"]')
            printf '%s\n' 'traceforge/otel-collector'
            ;;
        'module.foundation.kubernetes_service_account_v1.workload["traceforge-api"]')
            printf '%s\n' 'traceforge/traceforge-api'
            ;;
        'module.foundation.kubernetes_service_account_v1.workload["traceforge-worker"]')
            printf '%s\n' 'traceforge/traceforge-worker'
            ;;
        *)
            return 1
            ;;
    esac
}

check_foundation_state() {
    if ! foundation_state=$(terraform -chdir="$TERRAFORM_DIRECTORY" state list); then
        echo "failed to read Terraform state" >&2
        return 1
    fi
    if [ -z "$foundation_state" ]; then
        return 10
    fi

    while IFS= read -r address || [ -n "$address" ]; do
        if ! foundation_resource_id "$address" >/dev/null; then
            echo "Terraform state contains unexpected resource address: $address" >&2
            return 1
        fi
    done <<EOF
$foundation_state
EOF
}

require_foundation_state_namespace() {
    while IFS= read -r address || [ -n "$address" ]; do
        expected_resource_id=$(foundation_resource_id "$address")
        if ! state_resource=$(terraform -chdir="$TERRAFORM_DIRECTORY" state show -no-color "$address"); then
            echo "failed to inspect Terraform state address: $address" >&2
            exit 1
        fi
        if ! printf '%s\n' "$state_resource" | awk -v expected_id="$expected_resource_id" '
            $1 == "id" && $2 == "=" && $3 == "\"" expected_id "\"" { found = 1 }
            END { exit !found }
        '; then
            echo "Terraform state address targets an unexpected resource: $address" >&2
            exit 1
        fi
    done <<EOF
$foundation_state
EOF
}

require_foundation_state() {
    if check_foundation_state; then
        return 0
    fi
    state_status=$?
    if [ "$state_status" = "10" ]; then
        echo "Terraform foundation state is empty" >&2
    fi
    exit "$state_status"
}
