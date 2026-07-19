"""Small weather-agent subject used to prove exact replay end to end."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from traceforge.exceptions import SemanticValidationError
from traceforge.interfaces import DependencyAdapter


def _response(outcome: dict[str, Any], dependency: str) -> dict[str, Any]:
    if outcome["status"] == "errored":
        error = outcome["error"]
        raise SemanticValidationError(
            f"recorded {dependency} dependency errored: {error['type']}: {error['message']}"
        )
    response = outcome["response"]
    if not isinstance(response, dict):
        raise SemanticValidationError(f"recorded {dependency} response must be an object")
    return response


def run(invocation_input: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
    """Execute formatting and umbrella reasoning against recorded external facts."""
    question = invocation_input["question"]
    model_request = {
        "model": "controlled-weather-model",
        "payload": {"messages": [{"role": "user", "content": question}]},
    }
    model = _response(dependencies.invoke("model", "generate", model_request), "model")
    tool_call = model["payload"]["tool_call"]
    place = tool_call["arguments"]["place"]

    geocode_request = {
        "method": "GET",
        "url": "https://weather.invalid/geocode?" + urlencode({"place": place}),
        "headers": {"content-type": "application/json"},
        "body": None,
    }
    geocode = _response(dependencies.invoke("http", "GET", geocode_request), "geocoding")
    location = geocode["body"]

    weather_request = {
        "method": "GET",
        "url": "https://weather.invalid/current?"
        + urlencode({"latitude": location["latitude"], "longitude": location["longitude"]}),
        "headers": {"content-type": "application/json"},
        "body": None,
    }
    weather = _response(dependencies.invoke("http", "GET", weather_request), "weather")
    facts = weather["body"]
    umbrella_needed = facts["precipitation_probability"] >= 50
    advice = "Take an umbrella." if umbrella_needed else "An umbrella is not needed."

    return {
        "execution_status": "completed",
        "events": [
            {
                "event_id": "replay-model",
                "sequence": 1,
                "kind": "model",
                "name": "generate",
                "data": {"place": place},
            },
            {
                "event_id": "replay-geocode",
                "sequence": 2,
                "kind": "tool",
                "name": "geocode",
                "data": location,
            },
            {
                "event_id": "replay-weather",
                "sequence": 3,
                "kind": "tool",
                "name": "current_weather",
                "data": facts,
            },
        ],
        "output": {
            "place": place,
            "temperature_c": facts["temperature_c"],
            "umbrella_needed": umbrella_needed,
            "answer": f"{place}: {facts['temperature_c']}°C. {advice}",
        },
        "error": None,
    }
