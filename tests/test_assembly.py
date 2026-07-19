from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from traceforge.assembly import ConflictingDuplicateError, SequenceGapError, SQLiteAssemblyState
from traceforge.kafka_runtime import capsule_events
from traceforge.kafka_worker import KafkaAssemblyWorker
from traceforge.validation import validate_capsule

ROOT = Path(__file__).resolve().parents[1]


def _events() -> list[dict[str, Any]]:
    capsule = json.loads((ROOT / "examples/weather/replay-capsule.json").read_text())
    return capsule_events(capsule, "capture-test")


def test_assembly_duplicate_completion_and_reopening(tmp_path: Path) -> None:
    database, capsules = tmp_path / "state.sqlite3", tmp_path / "capsules"
    state = SQLiteAssemblyState(database, capsules)
    events = _events()
    assert state.process(events[0]).duplicate is False
    assert state.process(events[0]).duplicate is True
    for event in events[1:]:
        result = state.process(event)
    assert result.completed and result.capsule_path
    validate_capsule(json.loads(result.capsule_path.read_text()))
    state.close()
    reopened = SQLiteAssemblyState(database, capsules)
    assert reopened.capture("capture-test")["completed"] is True
    assert reopened.process(events[-1]).duplicate is True
    assert len(list(capsules.glob("*.json"))) == 1


def test_sequence_gap_and_conflicting_duplicate(tmp_path: Path) -> None:
    state = SQLiteAssemblyState(tmp_path / "state.sqlite3", tmp_path / "capsules")
    events = _events()
    with pytest.raises(SequenceGapError):
        state.process(events[1])
    state.process(events[0])
    conflict = copy.deepcopy(events[0])
    conflict["payload"]["capsule_id"] = "changed"
    with pytest.raises(ConflictingDuplicateError):
        state.process(conflict)


class Message:
    def __init__(self, value: bytes) -> None:
        self._value = value

    def value(self) -> bytes:
        return self._value

    def key(self) -> bytes:
        return b"capture-test"

    def error(self) -> None:
        return None


class Consumer:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self, message: Any, asynchronous: bool = False) -> None:
        assert message and asynchronous is False
        self.commits += 1

    def close(self) -> None:
        pass


class Dlq:
    def __init__(self, deliver: bool = True) -> None:
        self.callback: Any = None
        self.deliver = deliver

    def produce(self, topic: str, **kwargs: Any) -> None:
        self.callback = kwargs["on_delivery"]

    def poll(self, timeout: float) -> int:
        if self.callback:
            callback, self.callback = self.callback, None
            callback(None if self.deliver else RuntimeError(), object())
        return 0

    def flush(self, timeout: float) -> int:
        return 0


def test_worker_commits_after_persistence_and_confirmed_dlq(tmp_path: Path) -> None:
    consumer, dlq = Consumer(), Dlq()
    state = SQLiteAssemblyState(tmp_path / "state.sqlite3", tmp_path / "capsules")
    worker = KafkaAssemblyWorker(consumer, dlq, state, "dlq")
    assert worker.process_message(Message(json.dumps(_events()[0]).encode()))
    assert state.capture("capture-test") is not None
    assert consumer.commits == 1
    assert worker.process_message(Message(b"not-json"))
    assert consumer.commits == 2


def test_worker_does_not_commit_without_dlq_confirmation(tmp_path: Path) -> None:
    consumer = Consumer()
    worker = KafkaAssemblyWorker(
        consumer,
        Dlq(False),
        SQLiteAssemblyState(tmp_path / "state.sqlite3", tmp_path / "capsules"),
        "dlq",
    )
    assert worker.process_message(Message(b"bad")) is False
    assert consumer.commits == 0
