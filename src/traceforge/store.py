"""Local JSON storage used by the feasibility CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from traceforge.exceptions import StructuralValidationError


class JsonFileCapsuleStore:
    """Read and write UTF-8 JSON documents on the local filesystem."""

    def load(self, path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise StructuralValidationError(f"cannot read {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise StructuralValidationError(f"{path} is not valid JSON: {exc}") from exc

    def save(self, path: Path, value: Any) -> None:
        try:
            path.write_text(
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise StructuralValidationError(f"cannot write {path}: {exc}") from exc
