"""Local-only FastAPI dashboard application and trusted runner registry."""

from __future__ import annotations

import json
import re
import sysconfig
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from traceforge.examples.rag_agent import run as rag_runner
from traceforge.examples.tool_safety_agent import run as tool_safety_runner
from traceforge.examples.weather_agent import run as weather_runner
from traceforge.exceptions import (
    DependencyMismatchError,
    IntegrityError,
    LiveDependencyBlockedError,
    MissingDependencyError,
    SemanticValidationError,
    StructuralValidationError,
    TraceForgeError,
    UnexpectedDependencyError,
)
from traceforge.history import SQLiteReplayHistory
from traceforge.metrics import asgi_app
from traceforge.replay import CallableFrameworkAdapter, load_runner, replay_exact
from traceforge.workbench import SQLiteRunCatalog

MAX_UPLOAD_BYTES = 1_000_000
_RUNNER_ID = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
_RUNNER_REFERENCE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$")
_EXAMPLE_FILES = {
    "controlled-weather": ("weather/replay-capsule.json", "weather/regression-spec.json"),
    "rag-citation-grounding": (
        "rag-citation/replay-capsule.json",
        "rag-citation/regression-spec.json",
    ),
    "tool-argument-safety": (
        "tool-argument-safety/replay-capsule.json",
        "tool-argument-safety/regression-spec.json",
    ),
}


class RunnerRegistrationError(TraceForgeError):
    """Trusted local dashboard runner registration is invalid."""


@dataclass(frozen=True)
class RunnerMetadata:
    """Presentation and execution metadata for a pre-registered local runner."""

    runner_id: str
    name: str
    description: str
    classification: str
    adapter: CallableFrameworkAdapter
    has_example: bool = False

    def public(self) -> dict[str, Any]:
        return {
            "id": self.runner_id,
            "name": self.name,
            "description": self.description,
            "classification": self.classification,
            "has_example": self.has_example,
        }


def _builtins() -> dict[str, RunnerMetadata]:
    return {
        "controlled-weather": RunnerMetadata(
            "controlled-weather",
            "Weather Grounding",
            "Repair incorrect advice using recorded weather dependencies.",
            "Built-in demo",
            CallableFrameworkAdapter(weather_runner),
            has_example=True,
        ),
        "rag-citation-grounding": RunnerMetadata(
            "rag-citation-grounding",
            "RAG Citation Grounding",
            "Verify that answers remain supported by recorded evidence.",
            "Built-in demo",
            CallableFrameworkAdapter(rag_runner),
            has_example=True,
        ),
        "tool-argument-safety": RunnerMetadata(
            "tool-argument-safety",
            "Tool Argument Safety",
            "Detect consequential changes to approved tool arguments.",
            "Built-in demo",
            CallableFrameworkAdapter(tool_safety_runner),
            has_example=True,
        ),
    }


def _parse_registration(value: str) -> tuple[str, str]:
    runner_id, separator, reference = value.partition("=")
    if not separator or not runner_id or not reference or "=" in reference:
        raise RunnerRegistrationError(
            "dashboard runner must use ID=MODULE:FUNCTION registration syntax"
        )
    if not _RUNNER_ID.fullmatch(runner_id):
        raise RunnerRegistrationError(
            "dashboard runner ID must use lowercase letters, numbers, and hyphens"
        )
    if not _RUNNER_REFERENCE.fullmatch(reference):
        raise RunnerRegistrationError("dashboard runner target must use MODULE:FUNCTION syntax")
    return runner_id, reference


def build_runner_registry(registrations: Iterable[str] = ()) -> dict[str, RunnerMetadata]:
    """Resolve only startup-provided, trusted local runner registrations."""
    registry = _builtins()
    for registration in registrations:
        runner_id, reference = _parse_registration(registration)
        if runner_id in registry:
            raise RunnerRegistrationError(
                f"dashboard runner ID {runner_id!r} is already registered"
            )
        try:
            adapter = load_runner(reference)
        except SemanticValidationError as exc:
            raise RunnerRegistrationError(
                f"cannot register trusted local dashboard runner {runner_id!r}: {exc}"
            ) from exc
        registry[runner_id] = RunnerMetadata(
            runner_id,
            runner_id.replace("-", " ").title(),
            "Trusted local runner registered when this dashboard process started.",
            "Custom runner",
            adapter,
        )
    return registry


def _example_root() -> Path:
    """Find reviewed example data in an installed package or source checkout."""
    installed = Path(sysconfig.get_path("data")) / "share" / "traceforge" / "examples"
    if installed.is_dir():
        return installed
    return Path(__file__).resolve().parents[2] / "examples"


def load_builtin_example(runner_id: str) -> dict[str, Any]:
    """Load a fixed, reviewed built-in example; never accept a caller path."""
    try:
        capsule_name, specification_name = _EXAMPLE_FILES[runner_id]
    except KeyError as exc:
        raise KeyError("no built-in example is available for this runner") from exc
    root = _example_root()
    try:
        return {
            "capsule": json.loads((root / capsule_name).read_text(encoding="utf-8")),
            "spec": json.loads((root / specification_name).read_text(encoding="utf-8")),
        }
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("reviewed dashboard example data is unavailable") from exc


def _error(code: str, title: str, message: str, action: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "title": title, "message": message, "action": action}},
        status_code=status_code,
    )


def _replay_error(exc: Exception) -> tuple[str, str, str, str]:
    if isinstance(exc, json.JSONDecodeError):
        return (
            "invalid-json",
            "Invalid JSON",
            "TraceForge could not parse one of the evidence documents.",
            "Correct the JSON syntax, then run exact replay again.",
        )
    if isinstance(exc, StructuralValidationError):
        return (
            "structural-validation",
            "Structural validation failed",
            "The capsule or specification does not match the required document shape.",
            "Use a sealed Replay Capsule and a developer-approved regression specification.",
        )
    if isinstance(exc, SemanticValidationError):
        return (
            "semantic-validation",
            "Evidence validation failed",
            "The capsule or regression specification violates an exact replay rule.",
            "Use matching reviewed evidence and developer-approved expectations.",
        )
    if isinstance(exc, IntegrityError):
        return (
            "capsule-integrity",
            "Capsule integrity failed",
            "The immutable evidence no longer matches its recorded integrity data.",
            "Load the original sealed capsule; do not edit recorded evidence.",
        )
    if isinstance(exc, DependencyMismatchError):
        return (
            "dependency-mismatch",
            "Recorded dependency mismatch",
            "The runner requested a dependency that does not match the recorded sequence.",
            "Choose the matching runner and capsule, or capture new reviewed evidence.",
        )
    if isinstance(exc, (MissingDependencyError, UnexpectedDependencyError)):
        return (
            "dependency-consumption",
            "Recorded dependencies were not consumed exactly",
            "Exact replay requires the trusted runner and recorded dependency timeline to agree.",
            "Check the runner, capsule, and regression specification are from the same run.",
        )
    if isinstance(exc, LiveDependencyBlockedError):
        return (
            "live-dependency-blocked",
            "Live dependency blocked",
            "Exact replay never falls back to a live dependency.",
            "Record the required dependency outcome before retrying offline replay.",
        )
    return (
        "trusted-runner-failure",
        "Trusted runner failed",
        "The registered local runner could not complete the replay.",
        "Review the runner locally and try matching sanitized evidence again.",
    )


def create_app(
    database: Path,
    max_upload_bytes: int = MAX_UPLOAD_BYTES,
    runner_registrations: Iterable[str] = (),
    assembly_database: Path | None = None,
    capsule_directory: Path | None = None,
) -> FastAPI:
    """Create a dashboard with explicit local dependencies for easy testing."""
    package_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=package_dir / "templates")
    history = SQLiteReplayHistory(database)
    runs = SQLiteRunCatalog(assembly_database, capsule_directory)
    registry = build_runner_registry(runner_registrations)
    app = FastAPI(title="TraceForge Replay", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=package_dir / "static"), name="static")
    prometheus_app = asgi_app()
    if prometheus_app is not None:
        app.mount("/metrics", prometheus_app)

    @app.middleware("http")
    async def reject_large_uploads(request: Request, call_next: Any) -> Any:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_upload_bytes:
            return _error(
                "upload-too-large",
                "Upload is too large",
                "Evidence is limited to 1 MB for this local dashboard.",
                "Use a smaller sanitized capsule and specification.",
                413,
            )
        return await call_next(request)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> Any:
        catalog = runs.snapshot()
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "history": history.recent(),
                "run_source": catalog.source_dict(),
                "runs": [run.to_dict() for run in catalog.runs],
                "registered_runner_ids": tuple(registry),
                "runners": [metadata.public() for metadata in registry.values()],
            },
        )

    @app.get("/api/history")
    def replay_history() -> list[dict[str, Any]]:
        return [entry.__dict__ for entry in history.recent()]

    @app.get("/api/runs")
    def original_runs() -> list[dict[str, Any]]:
        return [run.to_dict() for run in runs.list()]

    @app.get("/api/run-source")
    def original_run_source() -> dict[str, Any]:
        return runs.snapshot().source_dict()

    @app.get("/api/runs/{run_id}")
    def original_run(run_id: str) -> JSONResponse:
        detail = runs.get(run_id)
        if detail is None:
            return _error(
                "run-not-found",
                "Original run not found",
                "No operational capture exists for this run ID.",
                "Choose a run from the local capture catalog.",
                404,
            )
        return JSONResponse(detail.to_dict())

    @app.get("/api/examples/{runner_id}")
    def example(runner_id: str) -> JSONResponse:
        if runner_id not in registry:
            return _error(
                "runner-not-registered",
                "Runner is not registered",
                "This dashboard can execute only runners registered at local startup.",
                "Restart the server with a trusted --runner registration.",
                404,
            )
        if not registry[runner_id].has_example:
            return _error(
                "example-unavailable",
                "No example is available",
                "Custom runners do not receive synthetic example evidence.",
                "Upload or paste reviewed evidence from your project.",
                404,
            )
        try:
            return JSONResponse(load_builtin_example(runner_id))
        except RuntimeError:
            return _error(
                "example-unavailable",
                "Example data is unavailable",
                "The reviewed built-in example could not be loaded.",
                "Install a complete TraceForge package and try again.",
                500,
            )

    @app.post("/api/replay")
    async def execute_replay(request: Request) -> JSONResponse:
        body = await request.body()
        if len(body) > max_upload_bytes:
            return _error(
                "upload-too-large",
                "Upload is too large",
                "Evidence is limited to 1 MB for this local dashboard.",
                "Use a smaller sanitized capsule and specification.",
                413,
            )
        payload: Any = None
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                return _error(
                    "invalid-json",
                    "Invalid JSON",
                    "TraceForge expects one JSON object containing replay evidence.",
                    "Send a JSON object with a runner, source mode, capsule, and specification.",
                    400,
                )
            mode = payload.get("source_mode")
            if mode not in {"example", "upload", "paste"}:
                return _error(
                    "ambiguous-input",
                    "Choose one evidence source",
                    "Use exactly one of Try example, Upload JSON, or Paste JSON.",
                    "Select one source mode and provide both required documents.",
                    400,
                )
            runner_name = payload.get("runner")
            if runner_name not in registry:
                return _error(
                    "runner-not-registered",
                    "Runner is not registered",
                    "HTTP requests cannot import or select arbitrary local code.",
                    "Choose a runner registered when this local server started.",
                    400,
                )
            if "capsule" not in payload or "spec" not in payload:
                return _error(
                    "missing-evidence",
                    "Evidence is incomplete",
                    "Exact replay requires both a Replay Capsule and a regression specification.",
                    "Add both documents before running exact replay.",
                    400,
                )
            capsule = payload["capsule"]
            spec = payload["spec"]
            result = replay_exact(capsule, registry[runner_name].adapter, spec)
            behavioural = result.regression is not None and result.regression.passed
            digest = (
                capsule.get("integrity", {}).get("digest", "unknown")
                if isinstance(capsule, dict)
                else "unknown"
            )
            history.append(
                capsule_digest=digest,
                runner=runner_name,
                technical_result=result.technical_status,
                behavioural_result="passed" if behavioural else "failed",
                error_summary=None,
            )
            response = result.to_dict()
            response["invocation"] = capsule["invocation"]
            response["dependencies"] = capsule["dependencies"]
            return JSONResponse(response)
        except Exception as exc:
            capsule = payload.get("capsule", {}) if isinstance(payload, dict) else {}
            digest = (
                capsule.get("integrity", {}).get("digest", "unknown")
                if isinstance(capsule, dict)
                else "unknown"
            )
            runner = payload.get("runner", "unknown") if isinstance(payload, dict) else "unknown"
            history.append(
                capsule_digest=digest,
                runner=str(runner),
                technical_result="errored",
                behavioural_result=None,
                error_summary=_replay_error(exc)[0],
            )
            return _error(*_replay_error(exc), 400)

    return app
