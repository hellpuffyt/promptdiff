"""Test-suite guard: promptdiff's tests must never call a real model.

Every runner used in the tests is either ReplayRunner (recorded fixtures)
or an explicitly labelled deterministic fake. This autouse fixture makes
that enforceable: any attempt to open a network connection fails the test.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("tests must not open network connections (no real LLM calls)")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    yield
