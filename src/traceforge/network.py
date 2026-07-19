"""Narrow process-wide network guard for offline exact replay."""

from __future__ import annotations

import socket
from contextlib import contextmanager
from threading import RLock
from typing import Any, Iterator

from traceforge.exceptions import LiveDependencyBlockedError

_guard_lock = RLock()


def _blocked(*args: Any, **kwargs: Any) -> None:
    del args, kwargs
    raise LiveDependencyBlockedError("live network access is blocked during exact replay")


@contextmanager
def block_network() -> Iterator[None]:
    """Temporarily block common socket entry points for trusted local runners."""
    with _guard_lock:
        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex
        original_create_connection = socket.create_connection
        original_getaddrinfo = socket.getaddrinfo
        socket.socket.connect = _blocked  # type: ignore[method-assign]
        socket.socket.connect_ex = _blocked  # type: ignore[method-assign]
        socket.create_connection = _blocked
        socket.getaddrinfo = _blocked
        try:
            yield
        finally:
            socket.socket.connect = original_connect  # type: ignore[method-assign]
            socket.socket.connect_ex = original_connect_ex  # type: ignore[method-assign]
            socket.create_connection = original_create_connection
            socket.getaddrinfo = original_getaddrinfo
