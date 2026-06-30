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
    httpd.shutdown()
    httpd.server_close()


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, json.loads(r.read())


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
