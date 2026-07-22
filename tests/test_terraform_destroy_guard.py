from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESTROY = ROOT / "scripts/terraform/destroy.sh"
EXPECTED_ADDRESSES = [
    "module.foundation.kubernetes_limit_range_v1.foundation",
    "module.foundation.kubernetes_namespace_v1.traceforge",
    "module.foundation.kubernetes_resource_quota_v1.foundation",
    'module.foundation.kubernetes_service_account_v1.workload["ingest-gateway"]',
    'module.foundation.kubernetes_service_account_v1.workload["kafka"]',
    'module.foundation.kubernetes_service_account_v1.workload["otel-collector"]',
    'module.foundation.kubernetes_service_account_v1.workload["traceforge-api"]',
    'module.foundation.kubernetes_service_account_v1.workload["traceforge-worker"]',
]


def _write_fake_commands(directory: Path) -> None:
    commands = {
        "kubectl": """#!/bin/sh
if [ "$1" = "config" ] && [ "$2" = "current-context" ]; then
    printf '%s\\n' "${FAKE_CONTEXT:-kind-traceforge}"
    exit 0
fi
exit 1
""",
        "kind": """#!/bin/sh
if [ "$1" = "get" ] && [ "$2" = "clusters" ]; then
    printf '%s\\n' "${FAKE_CLUSTER:-traceforge}"
    exit 0
fi
exit 1
""",
        "terraform": """#!/bin/sh
case "$2:$3" in
    state:list)
        if [ "${FAKE_STATE_LIST_FAILURE:-}" = "1" ]; then
            exit 42
        fi
        if [ -n "${FAKE_STATE:-}" ]; then
            printf '%s\\n' "$FAKE_STATE"
        fi
        ;;
    output:-raw)
        printf '%s\\n' "${FAKE_NAMESPACE_OUTPUT:-traceforge}"
        ;;
    state:show)
        case "$5" in
            module.foundation.kubernetes_limit_range_v1.foundation)
                resource_id=traceforge/traceforge-container-defaults
                ;;
            module.foundation.kubernetes_namespace_v1.traceforge)
                resource_id=traceforge
                ;;
            module.foundation.kubernetes_resource_quota_v1.foundation)
                resource_id=traceforge/traceforge-foundation
                ;;
            'module.foundation.kubernetes_service_account_v1.workload["ingest-gateway"]')
                resource_id=traceforge/ingest-gateway
                ;;
            'module.foundation.kubernetes_service_account_v1.workload["kafka"]')
                resource_id=traceforge/kafka
                ;;
            'module.foundation.kubernetes_service_account_v1.workload["otel-collector"]')
                resource_id=traceforge/otel-collector
                ;;
            'module.foundation.kubernetes_service_account_v1.workload["traceforge-api"]')
                resource_id=traceforge/traceforge-api
                ;;
            'module.foundation.kubernetes_service_account_v1.workload["traceforge-worker"]')
                resource_id=traceforge/traceforge-worker
                ;;
            *)
                exit 1
                ;;
        esac
        printf 'id = "%s"\\n' "$resource_id"
        ;;
    destroy:-auto-approve)
        printf 'destroy\\n' >>"$FAKE_COMMAND_LOG"
        ;;
    *)
        exit 1
        ;;
esac
""",
    }
    for name, content in commands.items():
        path = directory / name
        path.write_text(content)
        path.chmod(0o755)


def _run_destroy(
    tmp_path: Path,
    *,
    state: list[str] | None = None,
    context: str = "kind-traceforge",
    confirmation: str | None = "traceforge",
    state_list_failure: bool = False,
) -> tuple[subprocess.CompletedProcess[str], str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_commands(fake_bin)
    log = tmp_path / "commands.log"
    environment = os.environ | {
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "FAKE_COMMAND_LOG": str(log),
        "FAKE_CONTEXT": context,
        "FAKE_STATE": "\n".join(state or []),
        "FAKE_STATE_LIST_FAILURE": "1" if state_list_failure else "",
    }
    if confirmation is not None:
        environment["CONFIRM_TERRAFORM_DESTROY"] = confirmation
    else:
        environment.pop("CONFIRM_TERRAFORM_DESTROY", None)
    result = subprocess.run(
        [str(DESTROY)],
        cwd=ROOT,
        env=environment,
        check=False,
        text=True,
        capture_output=True,
    )
    return result, log.read_text() if log.exists() else ""


def test_destroy_accepts_full_expected_inventory(tmp_path: Path) -> None:
    result, log = _run_destroy(tmp_path, state=EXPECTED_ADDRESSES)

    assert result.returncode == 0, result.stderr
    assert log == "destroy\n"


def test_destroy_accepts_partial_expected_inventory(tmp_path: Path) -> None:
    result, log = _run_destroy(tmp_path, state=EXPECTED_ADDRESSES[:3])

    assert result.returncode == 0, result.stderr
    assert log == "destroy\n"


def test_destroy_accepts_one_expected_address(tmp_path: Path) -> None:
    result, log = _run_destroy(tmp_path, state=[EXPECTED_ADDRESSES[-1]])

    assert result.returncode == 0, result.stderr
    assert log == "destroy\n"


def test_destroy_handles_empty_state_without_destroy(tmp_path: Path) -> None:
    result, log = _run_destroy(tmp_path, state=[])

    assert result.returncode == 0, result.stderr
    assert "Terraform state is empty; nothing to destroy" in result.stdout
    assert log == ""


def test_destroy_rejects_unknown_state_address(tmp_path: Path) -> None:
    result, log = _run_destroy(tmp_path, state=["kubernetes_namespace_v1.unrelated"])

    assert result.returncode != 0
    assert "unexpected resource address" in result.stderr
    assert log == ""


def test_destroy_rejects_mixed_expected_and_unknown_addresses(tmp_path: Path) -> None:
    result, log = _run_destroy(
        tmp_path,
        state=[EXPECTED_ADDRESSES[0], "module.unrelated.kubernetes_secret_v1.value"],
    )

    assert result.returncode != 0
    assert "unexpected resource address" in result.stderr
    assert log == ""


def test_destroy_rejects_state_list_failure(tmp_path: Path) -> None:
    result, log = _run_destroy(tmp_path, state_list_failure=True)

    assert result.returncode != 0
    assert "failed to read Terraform state" in result.stderr
    assert log == ""


def test_destroy_rejects_wrong_context(tmp_path: Path) -> None:
    result, log = _run_destroy(
        tmp_path,
        state=[EXPECTED_ADDRESSES[0]],
        context="kind-another-project",
    )

    assert result.returncode != 0
    assert "expected kubectl context" in result.stderr
    assert log == ""


@pytest.mark.parametrize("confirmation", [None, "another-project"])
def test_destroy_rejects_missing_or_incorrect_confirmation(
    tmp_path: Path, confirmation: str | None
) -> None:
    result, log = _run_destroy(tmp_path, state=[EXPECTED_ADDRESSES[0]], confirmation=confirmation)

    assert result.returncode != 0
    assert "CONFIRM_TERRAFORM_DESTROY=traceforge" in result.stderr
    assert log == ""
