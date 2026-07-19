from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from traceforge.regression import evaluate_regression
from traceforge.replay import replay_exact


def test_core_import_does_not_import_langgraph() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, traceforge; assert 'langgraph' not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_langgraph_capture_and_exact_replay_offline() -> None:
    from traceforge.integrations.langgraph_weather import (
        LangGraphWeatherAdapter,
        capture_controlled_failure,
    )

    capsule = capture_controlled_failure()
    spec = {
        "version": "0.1.0",
        "assertions": [
            {"path": "output.place", "operator": "equals", "expected": "Kolkata"},
            {"path": "output.umbrella_needed", "operator": "equals", "expected": True},
        ],
    }
    result = replay_exact(capsule, LangGraphWeatherAdapter(), spec)
    assert result.regression is not None and result.regression.passed
    assert evaluate_regression(result.replay_observation, spec).passed


def test_complete_offline_workflow_exports_and_runs_pytest(tmp_path: Path) -> None:
    from traceforge.examples.end_to_end import run_workflow

    run_workflow(tmp_path)
    assert (tmp_path / "captured-weather.json").is_file()
    assert (tmp_path / "test_weather_regression.py").is_file()
