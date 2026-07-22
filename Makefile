.PHONY: kind-validate kind-create kind-images kind-apply kind-wait kind-smoke kind-destroy kind-verify terraform-fmt terraform-init terraform-validate terraform-test terraform-plan terraform-apply terraform-drift-check terraform-kustomize-apply terraform-kustomize-delete terraform-ownership-check terraform-destroy

TERRAFORM_DIRECTORY := infra/terraform/environments/kind

kind-validate:
	./scripts/kubernetes/validate.sh

kind-create:
	./scripts/kubernetes/create-cluster.sh

kind-images:
	./scripts/kubernetes/build-load-images.sh

kind-apply:
	./scripts/kubernetes/apply.sh

kind-wait:
	./scripts/kubernetes/wait-ready.sh

kind-smoke:
	./scripts/kubernetes/smoke.sh

kind-destroy:
	./scripts/kubernetes/destroy-cluster.sh

kind-verify: kind-validate kind-create kind-images kind-apply kind-wait kind-smoke

terraform-fmt:
	terraform fmt -check -recursive infra/terraform

terraform-init:
	./scripts/terraform/init.sh

terraform-validate:
	terraform -chdir=$(TERRAFORM_DIRECTORY) validate

terraform-test:
	terraform -chdir=$(TERRAFORM_DIRECTORY) test

terraform-plan:
	./scripts/terraform/plan.sh

terraform-apply:
	./scripts/terraform/apply.sh

terraform-drift-check:
	./scripts/terraform/drift-check.sh

terraform-kustomize-apply:
	./scripts/terraform/apply-kustomize.sh

terraform-kustomize-delete:
	./scripts/terraform/delete-kustomize.sh

terraform-ownership-check:
	./scripts/terraform/check-ownership.sh

terraform-destroy:
	./scripts/terraform/destroy.sh
