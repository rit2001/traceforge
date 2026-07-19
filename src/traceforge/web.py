"""Local-only FastAPI dashboard application."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from traceforge.examples.weather_agent import run as weather_runner
from traceforge.history import SQLiteReplayHistory
from traceforge.replay import CallableFrameworkAdapter, replay_exact

MAX_UPLOAD_BYTES = 1_000_000
RUNNERS = {"controlled-weather": CallableFrameworkAdapter(weather_runner)}


def create_app(database: Path, max_upload_bytes: int = MAX_UPLOAD_BYTES) -> FastAPI:
    """Create a dashboard with explicit local dependencies for easy testing."""
    package_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=package_dir / "templates")
    history = SQLiteReplayHistory(database)
    app = FastAPI(title="TraceForge Replay", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=package_dir / "static"), name="static")

    @app.middleware("http")
    async def reject_large_uploads(request: Request, call_next: Any) -> Any:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_upload_bytes:
            return JSONResponse({"error": "request exceeds upload-size limit"}, status_code=413)
        return await call_next(request)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> Any:
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {"history": history.recent(), "runners": sorted(RUNNERS)},
        )

    @app.get("/api/history")
    def replay_history() -> list[dict[str, Any]]:
        return [entry.__dict__ for entry in history.recent()]

    @app.post("/api/replay")
    async def execute_replay(request: Request) -> JSONResponse:
        body = await request.body()
        if len(body) > max_upload_bytes:
            return JSONResponse({"error": "request exceeds upload-size limit"}, status_code=413)
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("request must be a JSON object")
            runner_name = payload.get("runner")
            if runner_name not in RUNNERS:
                raise ValueError("runner is not registered for dashboard execution")
            capsule = payload["capsule"]
            spec = payload["spec"]
            result = replay_exact(capsule, RUNNERS[runner_name], spec)
            behavioural = result.regression is not None and result.regression.passed
            history.append(
                capsule_digest=capsule["integrity"]["digest"],
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
            capsule = (
                payload.get("capsule", {}) if isinstance(locals().get("payload"), dict) else {}
            )
            digest = (
                capsule.get("integrity", {}).get("digest", "unknown")
                if isinstance(capsule, dict)
                else "unknown"
            )
            runner = (
                payload.get("runner", "unknown")
                if isinstance(locals().get("payload"), dict)
                else "unknown"
            )
            history.append(
                capsule_digest=digest,
                runner=str(runner),
                technical_result="errored",
                behavioural_result=None,
                error_summary=str(exc)[:500],
            )
            return JSONResponse({"error": str(exc)}, status_code=400)

    return app
