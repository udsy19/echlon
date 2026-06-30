"""Local daemon HTTP plumbing (no model calls)."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from echlon import server


@pytest.fixture()
def base_url():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server._Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    host, port = httpd.server_address
    yield f"http://{host}:{port}"
    server._sessions.clear()
    httpd.shutdown()
    httpd.server_close()


def _get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(url: str, payload: dict):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_health(base_url) -> None:
    status, body = _get(f"{base_url}/health")
    assert status == 200 and body["status"] == "ok"


def test_run_requires_task(base_url) -> None:
    status, body = _post(f"{base_url}/run", {})
    assert status == 400 and "task" in body["error"]


def test_approve_unknown_session(base_url) -> None:
    status, body = _post(f"{base_url}/approve", {"session": "nope", "id": "a1", "decision": "deny"})
    assert status == 404


def test_cancel_and_status_unknown(base_url) -> None:
    assert _post(f"{base_url}/cancel", {"session": "nope"})[0] == 404
    assert _get(f"{base_url}/status?session=nope")[0] == 404


def test_run_rejects_bad_provider(base_url) -> None:
    status, body = _post(f"{base_url}/run", {"task": "x", "provider": "bogus"})
    assert status == 400 and "provider" in body["error"]


def test_run_rejects_bad_max_steps(base_url) -> None:
    status, body = _post(f"{base_url}/run", {"task": "x", "max_steps": 99999})
    assert status == 400 and "max_steps" in body["error"]


def test_run_rejects_invalid_json(base_url) -> None:
    req = urllib.request.Request(
        f"{base_url}/run", data=b"{not json", headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        raise AssertionError("expected 400")
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_message_unknown_session(base_url) -> None:
    assert _post(f"{base_url}/message", {"session": "nope", "text": "hi"})[0] == 404


def test_close_unknown_session(base_url) -> None:
    assert _post(f"{base_url}/close", {"session": "nope"})[0] == 404


def test_run_409_when_busy(base_url) -> None:
    # Inject a stand-in "running" session; /run must refuse a second.
    class _Busy:
        id = "busy01"
        status = "running"

    server._sessions["busy01"] = _Busy()
    try:
        status, body = _post(f"{base_url}/run", {"task": "x"})
        assert status == 409 and body["session_id"] == "busy01"
    finally:
        server._sessions.clear()
