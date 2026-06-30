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
from .logsetup import get_logger, setup_logging
from .models import ensure_ready
from .session import Session

log = get_logger(__name__)

_sessions: dict[str, Session] = {}
_MAX_BODY = 1 << 20  # 1 MiB request cap
_MAX_STEPS_LIMIT = 200
_MAX_SESSIONS = 64  # retain at most this many; oldest *finished* ones are evicted
_TERMINAL = ("done", "error", "cancelled")


def _active_session() -> Session | None:
    return next((s for s in _sessions.values() if s.status == "running"), None)


def _gc_sessions() -> int:
    """Evict the oldest finished sessions once the registry exceeds the cap.

    Running/pending sessions are never evicted (their event streams may still be
    consumed); only terminal ones are reclaimed, oldest first. Returns the count
    evicted. Without this the registry grows unbounded for the daemon's lifetime.
    """
    excess = len(_sessions) - _MAX_SESSIONS
    if excess <= 0:
        return 0
    evicted = 0
    for sid in [s for s, sess in _sessions.items() if sess.status in _TERMINAL]:
        if evicted >= excess:
            break
        del _sessions[sid]
        evicted += 1
    if evicted:
        log.debug("session gc", extra={"evicted": evicted, "remaining": len(_sessions)})
    return evicted


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
            q = parse_qs(parsed.query)
            try:
                start = int(q.get("from", ["0"])[0])
            except ValueError:
                start = 0
            return self._stream_events(q.get("session", [""])[0], start)
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
                os_control=body.get("os_control"),
            )
        except (ValueError, TypeError) as exc:
            return self._json(400, {"error": str(exc)})
        try:
            ensure_ready(cfg)
        except RuntimeError as exc:
            return self._json(400, {"error": str(exc)})
        _gc_sessions()
        session = Session(cfg, task).start()
        _sessions[session.id] = session
        log.info("run started", extra={"session": session.id, "model": cfg.model_id,
                                       "policy": cfg.policy_mode, "max_steps": cfg.max_steps})
        self._json(200, {"session_id": session.id})

    def _cancel(self, body: dict) -> None:
        session = _sessions.get(body.get("session", ""))
        if session is None:
            return self._json(404, {"error": "unknown session"})
        ok = session.cancel()
        log.info("run cancel requested", extra={"session": session.id, "ok": ok})
        self._json(200, {"ok": ok, "status": session.status})

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

    def _stream_events(self, session_id: str, start: int = 0) -> None:
        session = _sessions.get(session_id)
        if session is None:
            return self._json(404, {"error": "unknown session"})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        for event in session.events(start):
            chunk = f"data: {json.dumps(event.to_dict())}\n\n".encode("utf-8")
            try:
                self.wfile.write(chunk)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                break


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    setup_logging()
    httpd = ThreadingHTTPServer((host, port), _Handler)
    log.info("daemon listening", extra={"host": host, "port": port})
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        log.info("daemon stopped")
