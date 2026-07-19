"""Offline capture-to-generated-test demonstration."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from traceforge.export import export_pytest
from traceforge.integrations.langgraph_weather import (
    LangGraphWeatherAdapter,
    capture_controlled_failure,
)
from traceforge.replay import replay_exact
from traceforge.store import JsonFileCapsuleStore
from traceforge.validation import validate_capsule

SPEC = {
    "version": "0.1.0",
    "assertions": [
        {"path": "output.place", "operator": "equals", "expected": "Kolkata"},
        {"path": "output.umbrella_needed", "operator": "equals", "expected": True},
    ],
}


def run_workflow(output_dir: Path) -> None:
    """Capture, seal, validate, replay, evaluate, export, and run pytest offline."""
    output_dir.mkdir(parents=True, exist_ok=True)
    store = JsonFileCapsuleStore()
    capsule = capture_controlled_failure()
    capsule_path = output_dir / "captured-weather.json"
    spec_path = output_dir / "regression-spec.json"
    test_path = output_dir / "test_weather_regression.py"
    store.save(capsule_path, capsule)
    store.save(spec_path, SPEC)
    validate_capsule(capsule)
    result = replay_exact(capsule, LangGraphWeatherAdapter(), SPEC)
    if result.regression is None or not result.regression.passed:
        raise RuntimeError("controlled regression did not pass")
    export_pytest(
        capsule_path,
        "traceforge.integrations.langgraph_weather:run",
        spec_path,
        test_path,
        force=True,
    )
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(test_path)],
        check=False,
        capture_output=True,
        text=True,
        cwd=output_dir,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr)
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    run_workflow(Path("traceforge-demo-output"))
