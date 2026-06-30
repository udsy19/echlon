"""Thin local HTTP server exposing the Session API (PLAN.md §4-5).

Stdlib only (no web framework — keep the daemon lean). The Tauri UI talks to
this; so can curl. Endpoints:

  GET  /health                          -> {"status": "ok"}
  POST /run   {task, provider?, model?, policy_mode?, workspace?, max_steps?}
                                        -> {"session_id": "..."}
  GET  /events?session=<id>             -> text/event-stream of Session events
  POST /approve {session, id, decision} -> {"ok": bool}    decision: once|always|deny

Sessions run one at a time (module-level tool/policy state); the server keeps a
registry so a reconnecting client can resume the event stream.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import load_config
from .session import Session

_sessions: dict[str, Session] = {}
_MAX_BODY = 1 << 20  # 1 MiB request cap
_MAX_STEPS_LIMIT = 200


def _active_session() -> Session | None:
    return next((s for s in _sessions.values() if s.status == "running"), None)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # quiet by default
        pass

    # --- helpers ---
    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        if length > _MAX_BODY:
            return {"__error__": "request body too large"}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"__error__": "invalid JSON body"}

    # --- routes ---
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            return self._json(200, {"status": "ok"})
        if parsed.path == "/status":
            return self._status(parse_qs(parsed.query).get("session", [""])[0])
        if parsed.path == "/events":
            return self._stream_events(parse_qs(parsed.query).get("session", [""])[0])
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        body = self._read_json()
        if "__error__" in body:
            return self._json(400, {"error": body["__error__"]})
        if parsed.path == "/run":
            return self._start_run(body)
        if parsed.path == "/approve":
            return self._approve(body)
        if parsed.path == "/cancel":
            return self._cancel(body)
        self._json(404, {"error": "not found"})

    def _start_run(self, body: dict) -> None:
        task = body.get("task")
        if not task or not isinstance(task, str):
            return self._json(400, {"error": "missing or invalid 'task'"})
        max_steps = body.get("max_steps")
        if max_steps is not None and (not isinstance(max_steps, int) or not 1 <= max_steps <= _MAX_STEPS_LIMIT):
            return self._json(400, {"error": f"max_steps must be an int in 1..{_MAX_STEPS_LIMIT}"})
        active = _active_session()
        if active is not None:
            return self._json(409, {"error": "a session is already running", "session_id": active.id})
        try:
            cfg = load_config(
                provider=body.get("provider"),
                model_id=body.get("model"),
                workspace=body.get("workspace"),
                max_steps=max_steps,
                policy_mode=body.get("policy_mode"),
            )
        except (ValueError, TypeError) as exc:
            return self._json(400, {"error": str(exc)})
        session = Session(cfg, task).start()
        _sessions[session.id] = session
        self._json(200, {"session_id": session.id})

    def _cancel(self, body: dict) -> None:
        session = _sessions.get(body.get("session", ""))
        if session is None:
            return self._json(404, {"error": "unknown session"})
        self._json(200, {"ok": session.cancel(), "status": session.status})

    def _status(self, session_id: str) -> None:
        session = _sessions.get(session_id)
        if session is None:
            return self._json(404, {"error": "unknown session"})
        self._json(200, {"status": session.status, "result": str(session.result) if session.result is not None else None})

    def _approve(self, body: dict) -> None:
        session = _sessions.get(body.get("session", ""))
        if session is None:
            return self._json(404, {"error": "unknown session"})
        ok = session.decide(body.get("id", ""), body.get("decision", "deny"))
        self._json(200, {"ok": ok})

    def _stream_events(self, session_id: str) -> None:
        session = _sessions.get(session_id)
        if session is None:
            return self._json(404, {"error": "unknown session"})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        for event in session.events():
            chunk = f"data: {json.dumps(event.to_dict())}\n\n".encode("utf-8")
            try:
                self.wfile.write(chunk)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                break


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((host, port), _Handler)
    print(f"[echlon] daemon listening on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
