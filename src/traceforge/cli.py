"""Command-line interface for Replay Capsule sealing and validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from traceforge.exceptions import TraceForgeError
from traceforge.replay import load_runner, replay_exact
from traceforge.sealing import seal_capsule
from traceforge.store import JsonFileCapsuleStore
from traceforge.validation import validate_capsule

_STORE = JsonFileCapsuleStore()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="traceforge")
    commands = parser.add_subparsers(dest="command", required=True)

    seal = commands.add_parser("seal", help="seal a Replay Capsule draft")
    seal.add_argument("input", type=Path, metavar="INPUT")
    seal.add_argument("--output", required=True, type=Path, metavar="OUTPUT")

    validate = commands.add_parser("validate", help="validate a sealed Replay Capsule")
    validate.add_argument("capsule", type=Path, metavar="CAPSULE")

    replay = commands.add_parser("replay", help="run exact replay with trusted local code")
    replay.add_argument("capsule", type=Path, metavar="CAPSULE")
    replay.add_argument("--runner", required=True, metavar="MODULE:FUNCTION")
    replay.add_argument("--spec", required=True, type=Path, metavar="REGRESSION_SPEC")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "seal":
            sealed = seal_capsule(_STORE.load(args.input))
            _STORE.save(args.output, sealed)
            return 0

        if args.command == "validate":
            validate_capsule(_STORE.load(args.capsule))
            print("valid")
            return 0

        result = replay_exact(
            _STORE.load(args.capsule),
            load_runner(args.runner),
            _STORE.load(args.spec),
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
        return 0 if result.regression is None or result.regression.passed else 2
    except TraceForgeError as exc:
        print(f"traceforge: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
