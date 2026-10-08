"""Controlled framework-neutral portable execution span example."""

from __future__ import annotations

from typing import Any

from traceforge.capture import CaptureSession
from traceforge.interfaces import DependencyAdapter
from traceforge.sealing import seal_capsule

MODEL_REQUEST = {
    "model": "controlled-weather-model",
    "payload": {"messages": [{"role": "user", "content": "Weather in Kolkata?"}]},
}
HTTP_REQUEST = {
    "method": "GET",
    "url": "https://weather.invalid/current?place=Kolkata",
    "headers": {"content-type": "application/json"},
    "body": None,
}
WEATHER = {"place": "Kolkata", "temperature_c": 29, "condition": "rain"}
OUTPUT = {"answer": "Kolkata: 29°C and rain."}


def build_capsule() -> dict[str, Any]:
    """Build sealed historical evidence for the controlled structural example."""
    session = CaptureSession(
        schema_version="0.3.0",
        capsule_id="portable-spans-weather",
        run_id="portable-spans-weather-run",
        capture_kind="controlled_fixture",
        producer={"name": "traceforge-controlled-example", "version": "0.5.0"},
        subject={
            "application": "portable-weather-agent",
            "revision": "controlled-1",
            "framework": "custom-python",
            "language": "Python",
        },
        operation="answer_weather",
        invocation_input={"question": "Weather in Kolkata?"},
        recorded_at="2026-10-08T00:00:00Z",
    )
    with session.execution_span(
        "weather-agent", kind="agent", name="weather_agent", component="weather-agent"
    ):
        with session.execution_span(
            "reasoning-step",
            kind="step",
            name="reasoning_step",
            component="reasoner",
        ):
            session.record_model(
                "generate",
                MODEL_REQUEST,
                lambda request: {
                    "payload": {"selected_place": request["payload"]["messages"][0]["content"]}
                },
            )
        with session.execution_span(
            "weather-lookup",
            kind="step",
            name="weather_lookup",
            component="weather-client",
        ):
            session.record_http("GET", HTTP_REQUEST, lambda request: _weather_response(request))
        session.record_event("output", "final_answer", OUTPUT)
    return seal_capsule(session.finish("completed", OUTPUT))


def _weather_response(request: dict[str, Any]) -> dict[str, Any]:
    del request
    return {
        "status_code": 200,
        "headers": {"content-type": "application/json"},
        "body": WEATHER,
    }


def run(invocation_input: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
    """Replay the controlled behavior without reproducing historical span identifiers."""
    del invocation_input
    dependencies.invoke("model", "generate", MODEL_REQUEST)
    weather = dependencies.invoke("http", "GET", HTTP_REQUEST)["response"]["body"]
    assert weather == WEATHER
    return {
        "execution_status": "completed",
        "events": [
            {
                "event_id": "event-1",
                "sequence": 1,
                "kind": "output",
                "name": "final_answer",
                "data": OUTPUT,
            }
        ],
        "output": OUTPUT,
        "error": None,
    }
