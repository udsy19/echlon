"""Structured logging + session-registry GC (the long-running-daemon hardening)."""

from __future__ import annotations

import json
import logging

from echlon import server
from echlon.logsetup import JsonFormatter


def test_json_formatter_emits_one_parseable_line() -> None:
    rec = logging.makeLogRecord(
        {"name": "echlon.test", "levelno": logging.INFO, "levelname": "INFO",
         "msg": "hello %s", "args": ("world",)}
    )
    rec.session = "abcd1234"  # an `extra=` field
    line = JsonFormatter().format(rec)
    obj = json.loads(line)  # single JSON object, parseable
    assert obj["msg"] == "hello world"
    assert obj["level"] == "INFO"
    assert obj["logger"] == "echlon.test"
    assert obj["session"] == "abcd1234"  # extras are surfaced
    assert "ts" in obj


class _FakeSession:
    def __init__(self, sid: str, status: str) -> None:
        self.id = sid
        self.status = status


def _reset_registry(entries) -> None:
    server._sessions.clear()
    for s in entries:
        server._sessions[s.id] = s


def test_gc_evicts_oldest_finished_beyond_cap(monkeypatch) -> None:
    monkeypatch.setattr(server, "_MAX_SESSIONS", 3)
    _reset_registry([_FakeSession(f"s{i}", "closed") for i in range(5)])  # 5 > cap 3

    evicted = server._gc_sessions()

    assert evicted == 2
    assert list(server._sessions) == ["s2", "s3", "s4"]  # oldest two reclaimed


def test_gc_never_evicts_open_session(monkeypatch) -> None:
    monkeypatch.setattr(server, "_MAX_SESSIONS", 1)
    _reset_registry([
        _FakeSession("open", "running"),  # an open conversation (idle/running)
        _FakeSession("old", "closed"),
        _FakeSession("new", "closed"),
    ])

    server._gc_sessions()

    assert "open" in server._sessions  # the open conversation survives the GC
    assert "old" not in server._sessions  # closed ones are reclaimed first


def test_gc_noop_under_cap(monkeypatch) -> None:
    monkeypatch.setattr(server, "_MAX_SESSIONS", 10)
    _reset_registry([_FakeSession(f"s{i}", "closed") for i in range(3)])
    assert server._gc_sessions() == 0
    assert len(server._sessions) == 3
