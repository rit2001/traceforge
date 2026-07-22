# ADR-0006: Terraform and Kustomize Ownership

- Status: Accepted
- Date: 2026-07-22

## Context

TraceForge already has one verified native-Kustomize deployment of its existing containers on a
dedicated local kind cluster. The v0.4 milestone must demonstrate real Terraform state,
plan/apply/idempotency, drift reconciliation, and destroy without duplicating workload definitions,
creating cloud resources, or allowing two tools to manage the same Kubernetes object.

## Decision

Terraform uses only the official pinned `hashicorp/kubernetes` provider and owns exactly the local
foundation objects: namespace `traceforge`, one ResourceQuota, one LimitRange, and five dedicated
ServiceAccounts. ServiceAccount token automount is disabled because no workload needs Kubernetes
API access. The local environment uses the explicit `kind-traceforge` kubeconfig context and a
portable kubeconfig path variable.

Kustomize continues to own Deployments, the Kafka StatefulSet, Services, ConfigMaps, the PVC, and
all application configuration and security contexts. A shared workload base is rendered by two
overlays. The ordinary kind overlay supplies an equivalent Kustomize-owned foundation and remains
independently deployable. The Terraform-backed overlay omits every foundation kind and assumes
Terraform applied them first. Both overlays reuse the same workload definitions.

Terraform state is local and ignored for this development environment. The generated provider lock
file is committed. No secret belongs in variables, plans, state, logs, tests, or examples. A
production environment would require a protected remote backend with encryption, locking, access
control, backup, and tested recovery procedures.

## Consequences

- Terraform state and drift behavior are genuine for the bounded foundation resources.
- Applying or deleting Kustomize workloads cannot modify Terraform-owned objects.
- Application resources must be deleted before `terraform destroy`, because destroying the
  Terraform-owned namespace first would cascade-delete them.
- The local scripts reject any context or namespace other than `kind-traceforge`/`traceforge`.
- Terraform tests use mock providers and do not require Docker, kind, cloud credentials, or a live
  cluster in CI.
- Local kind apply does not prove AWS, EKS, cloud compatibility, production operations, high
  availability, scale, or security.

## Rejected Alternatives

### Terraform-Managing Workloads

Rejected because Kustomize already owns and verifies workload delivery. Moving or duplicating those
objects would enlarge state, duplicate manifests, and create field-ownership conflict.

### Shell Provisioners

Rejected. `null_resource`, `terraform_data`, `local-exec`, `remote-exec`, and shell provisioners do
not demonstrate provider-managed Kubernetes state and obscure ownership.

### Cloud Resources or Terraform Cloud

Rejected. This milestone is free, local, and limited to the existing kind cluster. It creates no
cloud account dependency or hosted state.
