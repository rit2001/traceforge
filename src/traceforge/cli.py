"""Command-line interface for Replay Capsule sealing and validation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from traceforge import __version__
from traceforge.exceptions import TraceForgeError
from traceforge.export import export_pytest
from traceforge.replay import load_runner, replay_exact
from traceforge.sealing import seal_capsule
from traceforge.store import JsonFileCapsuleStore
from traceforge.validation import validate_capsule

_STORE = JsonFileCapsuleStore()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="traceforge")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
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

    export = commands.add_parser("export-pytest", help="export an approved replay as pytest")
    export.add_argument("capsule", type=Path, metavar="CAPSULE")
    export.add_argument("--runner", required=True, metavar="MODULE:FUNCTION")
    export.add_argument("--spec", required=True, type=Path, metavar="REGRESSION_SPEC")
    export.add_argument("--output", required=True, type=Path, metavar="TEST_FILE")
    export.add_argument("--force", action="store_true")

    serve = commands.add_parser("serve", help="serve the local replay dashboard")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8000, type=int)
    serve.add_argument(
        "--runner",
        action="append",
        default=[],
        metavar="ID=MODULE:FUNCTION",
        help="register trusted local runner code at dashboard startup; may be repeated",
    )

    worker = commands.add_parser("worker", help="run an asynchronous capture worker")
    worker_commands = worker.add_subparsers(dest="worker_kind", required=True)
    kafka_worker = worker_commands.add_parser("kafka")
    kafka_worker.add_argument("--bootstrap-servers", required=True)
    kafka_worker.add_argument("--topic", default="traceforge.capture.v1")
    kafka_worker.add_argument("--dlq-topic", default="traceforge.capture.dlq.v1")
    kafka_worker.add_argument("--group-id", default="traceforge-assembler-v1")
    kafka_worker.add_argument("--database", required=True, type=Path)
    kafka_worker.add_argument("--capsule-directory", required=True, type=Path)

    smoke = commands.add_parser("kafka-smoke", help="run a bounded real-Kafka smoke capture")
    smoke.add_argument("--bootstrap-servers", required=True)
    smoke.add_argument("--database", required=True, type=Path)
    smoke.add_argument("--capsule-directory", required=True, type=Path)
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

        if args.command == "export-pytest":
            export_pytest(args.capsule, args.runner, args.spec, args.output, force=args.force)
            return 0

        if args.command == "serve":
            import uvicorn

            from traceforge.observability import configure, shutdown
            from traceforge.web import create_app

            telemetry_provider = configure("traceforge-api")
            try:
                uvicorn.run(
                    create_app(
                        Path(
                            os.environ.get(
                                "TRACEFORGE_HISTORY_PATH",
                                str(Path.cwd() / ".traceforge-history.sqlite3"),
                            )
                        ),
                        runner_registrations=args.runner,
                    ),
                    host=args.host,
                    port=args.port,
                )
            finally:
                shutdown(telemetry_provider)
            return 0

        if args.command == "worker":
            from traceforge.kafka_runtime import create_worker

            create_worker(
                args.bootstrap_servers,
                args.topic,
                args.dlq_topic,
                args.group_id,
                args.database,
                args.capsule_directory,
            ).run()
            return 0

        if args.command == "kafka-smoke":
            from traceforge.kafka_runtime import kafka_smoke

            print(kafka_smoke(args.bootstrap_servers, args.database, args.capsule_directory))
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
