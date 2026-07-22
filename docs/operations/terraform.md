# Local Terraform Operations

This runbook manages only the foundation for the dedicated local `traceforge` kind cluster. It does not create a cluster, build images, deliver workloads, or create cloud infrastructure. [ADR-0006](../decisions/ADR-0006-terraform-kustomize-ownership.md) owns the boundary.

## Ownership

Terraform owns exactly:

- the `traceforge` Namespace;
- one ResourceQuota and one LimitRange;
- the dedicated `ingest-gateway`, `kafka`, `traceforge-worker`, `traceforge-api`, and `otel-collector` ServiceAccounts; and
- foundation labels and outputs.

Kustomize owns Deployments, the Kafka StatefulSet, Services, ConfigMaps, the PVC, and application configuration. The ordinary `kind` overlay supplies a Kustomize foundation and remains independently deployable. The `terraform-kind` overlay omits every Terraform-owned object and expects the foundation to exist.

Terraform state for this development environment is local under `infra/terraform/environments/kind/` and ignored by Git. The generated `.terraform.lock.hcl` is committed so provider selection is reproducible. A production environment would require a protected remote backend with encryption, locking, access control, backup, tested recovery procedures, and a separately reviewed state-migration process.

Never place secret values in Terraform variables, plans, state, logs, outputs, or examples. The provider reads an explicit kubeconfig path and the fixed `kind-traceforge` context; source code embeds no certificates, tokens, or machine-specific absolute paths.

## Safe Lifecycle

Prerequisites are Terraform, Docker, kind, kubectl, and Kustomize support in kubectl. The lifecycle guards require the dedicated cluster name `traceforge`, context `kind-traceforge`, and namespace `traceforge`.

```sh
make terraform-fmt
make terraform-init
make terraform-validate
make terraform-test

make kind-create
make kind-images
make terraform-plan
make terraform-apply
terraform -chdir=infra/terraform/environments/kind state list

make terraform-ownership-check
make terraform-kustomize-apply
make kind-wait
make kind-smoke
make terraform-drift-check
```

`terraform-plan` saves the reviewed plan as the ignored `traceforge.tfplan`; `terraform-apply` applies that exact plan. `terraform-drift-check` uses `plan -detailed-exitcode`: exit 0 means no diff, exit 2 means drift, and exit 1 means an error.

To demonstrate bounded reconciliation, add only the documented disposable label to the Terraform-owned namespace, check for exit 2, re-plan and apply, then require exit 0:

```sh
kubectl --context kind-traceforge label namespace traceforge \
  traceforge.dev/drift-check=present --overwrite
make terraform-drift-check
make terraform-plan
make terraform-apply
make terraform-drift-check
```

Delete in ownership order. Removing the namespace first would implicitly delete Kustomize-owned resources and bypass their lifecycle:

```sh
CONFIRM_APPLICATION_DELETE=traceforge make terraform-kustomize-delete
CONFIRM_TERRAFORM_DESTROY=traceforge make terraform-destroy
terraform -chdir=infra/terraform/environments/kind state list
make kind-destroy
kind get clusters
```

The two confirmation values, exact context checks, and dedicated resource names prevent these scripts from targeting unrelated clusters or namespaces. Terraform native tests use a mock Kubernetes provider and leave no cluster resources. Real apply tests must still complete the ordered cleanup above.

## Failure Triage

- **Context guard fails:** inspect `kubectl config current-context`; do not bypass the guard or point this environment at another cluster.
- **Plan cannot contact Kubernetes:** confirm the dedicated cluster exists and `kubeconfig_path` resolves to the intended kubeconfig. Do not copy credentials into a variable file.
- **Kustomize apply reports missing ServiceAccounts:** apply the Terraform foundation before the `terraform-kind` overlay.
- **Quota rejects a workload:** compare explicit Pod requests/limits with the module quota. Change the typed quota input deliberately; do not remove requests or weaken the quota just to force admission.
- **Destroy reports namespace contents:** delete Kustomize-owned resources first, verify the application inventory is empty, and then retry the guarded Terraform destroy.
- **Provider startup fails in a restricted shell:** verify the provider checksum and platform, then run in an environment permitted to execute the downloaded signed provider. Do not replace it with an unpinned binary.

## Claim Boundary

Docker packages and runs individual containers. Kubernetes schedules, restarts, connects, configures, and constrains those containers. Terraform declares and tracks this small Kubernetes foundation; Kustomize remains the workload-delivery owner. Applying to local kind proves only a local Terraform lifecycle around a local Kubernetes deployment. It does not prove AWS, EKS, another cloud, production readiness, high availability, scale, durability, or security.
