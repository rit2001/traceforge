"""One controlled LangGraph integration for offline capture and replay."""

from __future__ import annotations

from typing import Any, TypedDict
from urllib.parse import urlencode

from langgraph.graph import END, START, StateGraph

from traceforge.capture import CaptureSession
from traceforge.examples.weather_agent import run as run_weather_logic
from traceforge.interfaces import DependencyAdapter
from traceforge.sealing import seal_capsule


class ReplayState(TypedDict, total=False):
    invocation: Any
    dependencies: DependencyAdapter
    observation: dict[str, Any]


class LangGraphWeatherAdapter:
    """Run the controlled weather subject through a real LangGraph graph."""

    def run(self, invocation_input: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        graph = StateGraph(ReplayState)

        def weather_node(state: ReplayState) -> ReplayState:
            return {"observation": run_weather_logic(state["invocation"], state["dependencies"])}

        graph.add_node("weather", weather_node)
        graph.add_edge(START, "weather")
        graph.add_edge("weather", END)
        result = graph.compile().invoke(
            {"invocation": invocation_input, "dependencies": dependencies}
        )
        return result["observation"]


def run(invocation_input: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
    """Function entry point suitable for CLI and exported regression tests."""
    return LangGraphWeatherAdapter().run(invocation_input, dependencies)


def capture_controlled_failure() -> dict[str, Any]:
    """Capture a credential-free failed weather answer through LangGraph."""
    session = CaptureSession(
        capsule_id="langgraph-weather-controlled-v0",
        run_id="langgraph-weather-run-1",
        capture_kind="controlled_fixture",
        producer={"name": "traceforge-replay", "version": "0.1.0"},
        subject={
            "application": "langgraph-weather-example",
            "revision": "product-completion",
            "framework": "LangGraph",
            "language": "Python",
        },
        operation="answer_weather_question",
        invocation_input={
            "question": "What is the weather in Kolkata, and should I carry an umbrella?"
        },
        recorded_at="2026-07-19T00:00:00Z",
    )

    class CaptureState(TypedDict, total=False):
        output: dict[str, Any]

    graph = StateGraph(CaptureState)

    def capture_node(state: CaptureState) -> CaptureState:
        del state
        question = "What is the weather in Kolkata, and should I carry an umbrella?"
        model_request = {
            "model": "controlled-weather-model",
            "payload": {"messages": [{"role": "user", "content": question}]},
        }
        session.record_model(
            "generate",
            model_request,
            lambda request: {
                "payload": {
                    "tool_call": {
                        "name": "get_weather",
                        "arguments": {"place": "Kolkata"},
                    }
                }
            },
        )
        geocode_request = {
            "method": "GET",
            "url": "https://weather.invalid/geocode?" + urlencode({"place": "Kolkata"}),
            "headers": {"content-type": "application/json"},
            "body": None,
        }
        session.record_http(
            "GET",
            geocode_request,
            lambda request: {
                "status_code": 200,
                "headers": {"content-type": "application/json"},
                "body": {"place": "Kolkata", "latitude": 22.5726, "longitude": 88.3639},
            },
        )
        weather_request = {
            "method": "GET",
            "url": "https://weather.invalid/current?"
            + urlencode({"latitude": 22.5726, "longitude": 88.3639}),
            "headers": {"content-type": "application/json"},
            "body": None,
        }
        session.record_http(
            "GET",
            weather_request,
            lambda request: {
                "status_code": 200,
                "headers": {"content-type": "application/json"},
                "body": {"temperature_c": 29, "precipitation_probability": 80},
            },
        )
        session.record_event("node", "incorrect_advice", {"place": "Kolkata"})
        return {
            "output": {
                "place": "Kolkata",
                "temperature_c": 29,
                "umbrella_needed": False,
                "answer": "Kolkata: 29°C. An umbrella is not needed.",
            }
        }

    graph.add_node("capture_weather", capture_node)
    graph.add_edge(START, "capture_weather")
    graph.add_edge("capture_weather", END)
    result = graph.compile().invoke({})
    return seal_capsule(session.finish("completed", result["output"], None))
