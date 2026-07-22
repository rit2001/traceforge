from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "deploy/kubernetes/base"
KIND = ROOT / "deploy/kubernetes/overlays/kind"
TERRAFORM_KIND = ROOT / "deploy/kubernetes/overlays/terraform-kind"
KUSTOMIZE_FOUNDATION = ROOT / "deploy/kubernetes/foundation/kustomize"
KIND_COMPONENT = ROOT / "deploy/kubernetes/components/kind-local"


def _manifests() -> dict[str, str]:
    return {path.name: path.read_text() for path in sorted(BASE.glob("*.yaml"))}


def test_kustomize_references_existing_base_resources() -> None:
    kustomization = (BASE / "kustomization.yaml").read_text()
    resource_names = re.findall(r"^  - ([\w-]+\.yaml)$", kustomization, flags=re.MULTILINE)
    assert resource_names
    assert all((BASE / name).is_file() for name in resource_names)
    assert "../../base" in (KIND / "kustomization.yaml").read_text()
    assert "../../foundation/kustomize" in (KIND / "kustomization.yaml").read_text()
    assert "../../base" in (TERRAFORM_KIND / "kustomization.yaml").read_text()
    assert "foundation/kustomize" not in (TERRAFORM_KIND / "kustomization.yaml").read_text()
    assert "name: traceforge" in (KIND / "cluster.yaml").read_text()


def test_workloads_have_explicit_images_resources_probes_and_security() -> None:
    workloads = {
        name: text
        for name, text in _manifests().items()
        if name.endswith(("deployment.yaml", "statefulset.yaml"))
    }
    assert len(workloads) == 5
    for name, text in workloads.items():
        images = re.findall(r"^\s+image: (\S+)$", text, flags=re.MULTILINE)
        assert images, name
        assert all(":" in image and not image.endswith(":latest") for image in images), name
        assert "requests:" in text and "limits:" in text, name
        assert "startupProbe:" in text, name
        assert "readinessProbe:" in text, name
        assert "livenessProbe:" in text, name
        assert "allowPrivilegeEscalation: false" in text, name
        assert "type: RuntimeDefault" in text, name
        assert re.search(r"capabilities:\n\s+drop:\n\s+- ALL", text), name


def test_application_workloads_use_uid_gid_10001_and_read_only_root() -> None:
    for name in (
        "ingest-gateway-deployment.yaml",
        "worker-deployment.yaml",
        "api-deployment.yaml",
    ):
        text = (BASE / name).read_text()
        assert "runAsNonRoot: true" in text
        assert "runAsUser: 10001" in text
        assert "runAsGroup: 10001" in text
        assert "readOnlyRootFilesystem: true" in text
        assert "terminationGracePeriodSeconds:" in text


def test_workloads_use_dedicated_service_accounts_without_tokens() -> None:
    expected = {
        "ingest-gateway-deployment.yaml": "ingest-gateway",
        "kafka-statefulset.yaml": "kafka",
        "worker-deployment.yaml": "traceforge-worker",
        "api-deployment.yaml": "traceforge-api",
        "otel-collector-deployment.yaml": "otel-collector",
    }
    for name, service_account in expected.items():
        text = (BASE / name).read_text()
        assert f"serviceAccountName: {service_account}" in text
        assert "automountServiceAccountToken: false" in text


def test_worker_state_is_single_writer_and_kind_pvc_is_local() -> None:
    worker = (BASE / "worker-deployment.yaml").read_text()
    claim = (BASE / "persistent-volume-claim.yaml").read_text()
    overlay_claim = (KIND_COMPONENT / "persistent-volume-claim.yaml").read_text()
    assert "replicas: 1" in worker
    assert "type: Recreate" in worker
    assert "claimName: traceforge-data" in worker
    assert "ReadWriteOnce" in claim
    assert "storageClassName: standard" in overlay_claim


def test_kafka_headless_service_publishes_bootstrap_dns_before_readiness() -> None:
    service = (BASE / "kafka-service.yaml").read_text()
    assert "clusterIP: None" in service
    assert "publishNotReadyAddresses: true" in service


def test_only_required_cluster_services_and_no_secret_objects() -> None:
    manifests = _manifests()
    services = {
        name
        for name, text in manifests.items()
        if re.search(r"^kind: Service$", text, flags=re.MULTILINE)
    }
    assert services == {
        "api-service.yaml",
        "ingest-gateway-service.yaml",
        "kafka-service.yaml",
        "otel-collector-service.yaml",
    }
    combined = "\n".join(manifests.values())
    assert "kind: Secret" not in combined
    assert "secretKeyRef:" not in combined
    assert "type: LoadBalancer" not in combined
    assert "traceforge.dev/infrastructure: local-development" in combined


def test_kustomize_foundation_matches_terraform_object_boundary() -> None:
    kustomization = (KUSTOMIZE_FOUNDATION / "kustomization.yaml").read_text()
    assert "namespace.yaml" in kustomization
    assert "resource-quota.yaml" in kustomization
    assert "limit-range.yaml" in kustomization
    assert "service-accounts.yaml" in kustomization
    accounts = (KUSTOMIZE_FOUNDATION / "service-accounts.yaml").read_text()
    assert accounts.count("kind: ServiceAccount") == 5
    assert accounts.count("automountServiceAccountToken: false") == 5
    terraform_overlay = (TERRAFORM_KIND / "kustomization.yaml").read_text()
    for owned_kind in ("Namespace", "ResourceQuota", "LimitRange", "ServiceAccount"):
        assert owned_kind not in terraform_overlay


def test_collector_configuration_reuses_compose_configuration() -> None:
    assert (BASE / "otel-collector-config.yaml").read_text() == (
        ROOT / "services/otel-collector.yaml"
    ).read_text()


def test_lifecycle_scripts_are_fixed_to_the_dedicated_cluster() -> None:
    scripts = {
        path.name: path.read_text() for path in sorted((ROOT / "scripts/kubernetes").glob("*.sh"))
    }
    assert scripts
    assert "CLUSTER_NAME=traceforge" in scripts["common.sh"]
    assert "KUBE_CONTEXT=kind-traceforge" in scripts["common.sh"]
    assert 'kind delete cluster --name "$CLUSTER_NAME"' in scripts["destroy-cluster.sh"]
    assert "delete clusters" not in scripts["destroy-cluster.sh"]
    for name, text in scripts.items():
        assert "set -eu" in text, name


def test_terraform_lifecycle_scripts_guard_ownership_and_destructive_actions() -> None:
    scripts = {
        path.name: path.read_text() for path in sorted((ROOT / "scripts/terraform").glob("*.sh"))
    }
    assert scripts
    common = scripts["common.sh"]
    assert "EXPECTED_CLUSTER=traceforge" in common
    assert "EXPECTED_CONTEXT=kind-traceforge" in common
    assert "EXPECTED_NAMESPACE=traceforge" in common
    assert "Terraform state contains unexpected resource address" in common
    assert "require_foundation_state" in scripts["apply-kustomize.sh"]
    assert "require_foundation_state" in scripts["delete-kustomize.sh"]
    assert "CONFIRM_APPLICATION_DELETE" in scripts["delete-kustomize.sh"]
    assert "CONFIRM_TERRAFORM_DESTROY" in scripts["destroy.sh"]
    for name, text in scripts.items():
        assert "set -eu" in text, name


def test_terraform_uses_provider_resources_without_shell_provisioners() -> None:
    terraform = "\n".join(
        path.read_text()
        for path in sorted((ROOT / "infra/terraform").rglob("*.tf"))
        if ".terraform" not in path.parts
    )
    assert 'source  = "hashicorp/kubernetes"' in terraform
    assert 'version = "~> 2.38.0"' in terraform
    for prohibited in (
        'resource "null_resource"',
        'resource "terraform_data"',
        'provisioner "local-exec"',
        'provisioner "remote-exec"',
    ):
        assert prohibited not in terraform
