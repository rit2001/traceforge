from __future__ import annotations

import json
from pathlib import Path

from traceforge.cli import main

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_cli_seal_then_validate(capsule_draft: dict, tmp_path: Path, capsys) -> None:
    draft_path = tmp_path / "draft.json"
    sealed_path = tmp_path / "sealed.json"
    draft_path.write_text(json.dumps(capsule_draft), encoding="utf-8")

    assert main(["seal", str(draft_path), "--output", str(sealed_path)]) == 0
    assert main(["validate", str(sealed_path)]) == 0
    assert capsys.readouterr().out == "valid\n"


def test_cli_validate_reports_failure(capsule_draft: dict, tmp_path: Path, capsys) -> None:
    capsule_path = tmp_path / "invalid.json"
    capsule_path.write_text(json.dumps(capsule_draft), encoding="utf-8")

    assert main(["validate", str(capsule_path)]) == 1
    assert "traceforge:" in capsys.readouterr().err


def test_cli_exact_replay(capsys) -> None:
    capsule = REPOSITORY_ROOT / "examples" / "weather" / "replay-capsule.json"
    spec = REPOSITORY_ROOT / "examples" / "weather" / "regression-spec.json"

    exit_code = main(
        [
            "replay",
            str(capsule),
            "--runner",
            "traceforge.examples.weather_agent:run",
            "--spec",
            str(spec),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["regression"]["passed"] is True
