from __future__ import annotations

import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from traceforge.examples.weather_agent import run as weather_runner
from traceforge.export import (
    ExportError,
    export_pytest,
    render_pytest,
    render_regression_bundle,
)
from traceforge.promotion import promote_regression
from traceforge.replay import CallableFrameworkAdapter, replay_exact

ROOT = Path(__file__).resolve().parents[1]
CAPSULE = ROOT / "examples/weather/replay-capsule.json"
SPEC = ROOT / "examples/weather/regression-spec.json"
RUNNER = "traceforge.examples.weather_agent:run"


def test_exported_pytest_is_deterministic_and_executable(tmp_path: Path) -> None:
    output = tmp_path / "test_exported.py"
    export_pytest(CAPSULE, RUNNER, SPEC, output)
    first = output.read_text(encoding="utf-8")
    export_pytest(CAPSULE, RUNNER, SPEC, output, force=True)
    assert output.read_text(encoding="utf-8") == first

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(output)],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr


def test_export_refuses_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "test_exported.py"
    output.write_text("keep\n", encoding="utf-8")
    with pytest.raises(ExportError, match="--force"):
        export_pytest(CAPSULE, RUNNER, SPEC, output)
    assert output.read_text(encoding="utf-8") == "keep\n"


def test_export_preserves_relative_references_parent_creation_and_explicit_force(
    tmp_path: Path,
) -> None:
    capsule = tmp_path / "evidence" / "capsule.json"
    spec = tmp_path / "expectations" / "spec.json"
    output = tmp_path / "generated" / "nested" / "test_regression.py"
    capsule.parent.mkdir()
    spec.parent.mkdir()
    capsule.write_text("{}", encoding="utf-8")
    spec.write_text("{}", encoding="utf-8")

    export_pytest(capsule, RUNNER, spec, output)
    source = output.read_text(encoding="utf-8")

    assert "../../evidence/capsule.json" in source
    assert "../../expectations/spec.json" in source
    output.write_text("occupied\n", encoding="utf-8")
    with pytest.raises(ExportError):
        export_pytest(capsule, RUNNER, spec, output)
    export_pytest(capsule, RUNNER, spec, output, force=True)
    assert output.read_text(encoding="utf-8") == source


def test_export_renderer_is_the_single_deterministic_source() -> None:
    source = render_pytest("replay-capsule.json", RUNNER, "regression-spec.json")

    assert source == render_pytest("replay-capsule.json", RUNNER, "regression-spec.json")
    assert "result = replay_exact(" in source
    assert "assert result.regression.passed" in source
    assert "requests" not in source
    assert "http" not in source


def test_renderer_treats_references_as_string_literals_not_python_source(tmp_path: Path) -> None:
    marker = tmp_path / "injected"
    attack = f"x'\n__import__('pathlib').Path({str(marker)!r}).write_text('bad')\n#\\☃"

    source = render_pytest(attack, attack, attack)

    compile(source, "generated.py", "exec")
    namespace: dict[str, object] = {}
    exec(source, namespace)
    assert marker.exists() is False
    assert repr(attack) in source


def test_regression_bundle_is_atomic_deterministic_and_path_safe() -> None:
    capsule = json.loads(CAPSULE.read_text(encoding="utf-8"))
    spec = json.loads(SPEC.read_text(encoding="utf-8"))

    first = render_regression_bundle(capsule, spec, RUNNER)
    second = render_regression_bundle(capsule, spec, RUNNER)

    assert first == second
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        assert archive.namelist() == [
            "replay-capsule.json",
            "regression-spec.json",
            "test_traceforge_regression.py",
        ]
        assert all(
            not name.startswith(("/", "../")) and "/../" not in name for name in archive.namelist()
        )
        assert json.loads(archive.read("replay-capsule.json")) == capsule
        assert json.loads(archive.read("regression-spec.json")) == spec
        source = archive.read("test_traceforge_regression.py").decode()
        assert source == render_pytest("replay-capsule.json", RUNNER, "regression-spec.json")


def test_promoted_repaired_weather_export_passes_fails_then_passes(
    tmp_path: Path,
) -> None:
    capsule = json.loads(CAPSULE.read_text(encoding="utf-8"))
    result = replay_exact(capsule, CallableFrameworkAdapter(weather_runner))
    promoted = promote_regression(
        result,
        [{"path": "output.umbrella_needed", "operator": "equals", "expected": True}],
        developer_approved=True,
    )
    capsule_path = tmp_path / "replay-capsule.json"
    spec_path = tmp_path / "regression-spec.json"
    runner_path = tmp_path / "promotion_runner.py"
    test_path = tmp_path / "test_traceforge_regression.py"
    capsule_path.write_text(json.dumps(capsule), encoding="utf-8")
    spec_path.write_text(json.dumps(promoted), encoding="utf-8")
    offline_runner = (
        "import socket\n"
        "from traceforge.examples.weather_agent import run as repaired\n"
        "from traceforge.exceptions import LiveDependencyBlockedError\n"
        "def run(invocation_input, dependencies):\n"
        "    try:\n"
        "        socket.create_connection(('live.invalid', 443))\n"
        "    except LiveDependencyBlockedError:\n"
        "        return repaired(invocation_input, dependencies)\n"
        "    raise AssertionError('live network was not blocked')\n"
    )
    runner_path.write_text(offline_runner, encoding="utf-8")
    export_pytest(capsule_path, "promotion_runner:run", spec_path, test_path)

    def run_exported() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-B", "-m", "pytest", "--assert=plain", "-q", str(test_path)],
            check=False,
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )

    passing = run_exported()
    assert passing.returncode == 0, passing.stdout + passing.stderr

    runner_path.write_text(
        "from traceforge.examples.weather_agent import run as repaired\n"
        "def run(invocation_input, dependencies):\n"
        "    result = repaired(invocation_input, dependencies)\n"
        "    result['output']['umbrella_needed'] = False\n"
        "    return result\n",
        encoding="utf-8",
    )
    failing = run_exported()
    assert failing.returncode != 0
    assert "1 failed" in failing.stdout

    runner_path.write_text(offline_runner, encoding="utf-8")
    restored = run_exported()
    assert restored.returncode == 0, restored.stdout + restored.stderr

    runner_path.write_text(
        "def run(invocation_input, dependencies):\n"
        "    dependencies.invoke('model', 'generate', {'model': 'mismatched'})\n"
        "    raise AssertionError('dependency mismatch did not fail closed')\n",
        encoding="utf-8",
    )
    mismatched = run_exported()
    assert mismatched.returncode != 0
    assert "DependencyMismatchError" in mismatched.stdout
