.PHONY: kind-validate kind-create kind-images kind-apply kind-wait kind-smoke kind-destroy kind-verify

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
