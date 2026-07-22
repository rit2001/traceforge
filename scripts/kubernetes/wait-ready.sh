#!/bin/sh

set -eu
. "$(dirname -- "$0")/common.sh"

require_command kubectl
require_cluster

kubectl --context "$KUBE_CONTEXT" wait --for=condition=Available deployment/otel-collector \
    --namespace "$KUBE_NAMESPACE" --timeout=180s
kubectl --context "$KUBE_CONTEXT" rollout status statefulset/kafka \
    --namespace "$KUBE_NAMESPACE" --timeout=300s
kubectl --context "$KUBE_CONTEXT" wait --for=jsonpath='{.status.phase}'=Bound \
    persistentvolumeclaim/traceforge-data --namespace "$KUBE_NAMESPACE" --timeout=180s
kubectl --context "$KUBE_CONTEXT" rollout status deployment/ingest-gateway \
    --namespace "$KUBE_NAMESPACE" --timeout=180s
kubectl --context "$KUBE_CONTEXT" rollout status deployment/traceforge-worker \
    --namespace "$KUBE_NAMESPACE" --timeout=180s
kubectl --context "$KUBE_CONTEXT" rollout status deployment/traceforge-api \
    --namespace "$KUBE_NAMESPACE" --timeout=180s
kubectl --context "$KUBE_CONTEXT" get pods --namespace "$KUBE_NAMESPACE"
