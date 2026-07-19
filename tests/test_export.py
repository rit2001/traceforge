from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from traceforge.export import ExportError, export_pytest

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
