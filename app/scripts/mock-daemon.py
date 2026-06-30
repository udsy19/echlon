#!/usr/bin/env python3
"""Mock echlon daemon — exercises the desktop console without a real agent/API key.

Speaks the exact contract the UI consumes (daemon/README.md):
  GET  /health                          -> {"status":"ok"}
  POST /run    {task, ...}              -> {"session_id": "..."}
  GET  /events?session=<id>             -> SSE: started/plan/tool_call/step/
                                           approval_request/final_answer/done
  POST /approve {session, id, decision} -> {"ok": bool}

It scripts a believable run that includes a risky action, so you can watch the
event stream render and answer the approval prompt end-to-end.

    python3 scripts/mock-daemon.py        # http://127.0.0.1:8765
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

_sessions: dict[str, "MockSession"] = {}


class MockSession:
    def __init__(self, task: str) -> None:
        self.id = uuid.uuid4().hex[:8]
        self.task = task
        self.q: queue.Queue[dict | None] = queue.Queue()
        self.decisions: dict[str, queue.Queue[str]] = {}

    def emit(self, type_: str, data: dict | None = None) -> None:
        self.q.put({"type": type_, "data": data or {}})

    def decide(self, approval_id: str, decision: str) -> bool:
        dq = self.decisions.get(approval_id)
        if dq is None:
            return False
        dq.put(decision)
        return True

    def start(self) -> "MockSession":
        threading.Thread(target=self._run, daemon=True).start()
        return self

    def _run(self) -> None:
        self.emit("started", {"task": self.task, "model": "anthropic/claude-opus-4-8 (mock)"})
        time.sleep(0.6)
        self.emit("plan", {"plan": "1. Inspect the workspace.\n2. Create the script.\n3. Run it and fix errors."})
        time.sleep(0.6)
        self.emit("tool_call", {"name": "shell_exec", "arguments": "{'command': 'ls -la'}"})
        time.sleep(0.5)
        self.emit("step", {"step": 1, "observations": "total 0\ndrwxr-xr-x  workspace empty", "error": None})
        time.sleep(0.6)
        self.emit("tool_call", {"name": "file_write", "arguments": "{'path': 'primes.py', 'content': '...'}"})
        time.sleep(0.5)
        self.emit("step", {"step": 2, "observations": "Wrote 18 lines to primes.py", "error": None})
        time.sleep(0.6)

        # A risky action that blocks on approval.
        aid = "a1"
        dq: queue.Queue[str] = queue.Queue()
        self.decisions[aid] = dq
        self.emit("tool_call", {"name": "shell_exec", "arguments": "{'command': 'rm -rf ./build'}"})
        self.emit("approval_request", {"id": aid, "summary": "Run a destructive shell command: rm -rf ./build"})
        decision = dq.get()  # blocks until the UI answers
        self.decisions.pop(aid, None)

        if decision == "deny":
            self.emit("step", {"step": 3, "observations": "", "error": "Action denied by policy; adapting."})
            time.sleep(0.5)
            self.emit("step", {"step": 4, "observations": "Skipped cleanup, continued without it.", "error": None})
        else:
            self.emit("step", {"step": 3, "observations": "Removed ./build", "error": None})

        time.sleep(0.6)
        self.emit("tool_call", {"name": "shell_exec", "arguments": "{'command': 'python primes.py'}"})
        time.sleep(0.5)
        self.emit("step", {"step": 5, "observations": "2 3 5 7 11 13 17 19 23 29 31 37 41 43 47 53 59 61 67 71", "error": None})
        time.sleep(0.6)
        self.emit("final_answer", {"output": "Done. primes.py prints the first 20 primes and runs cleanly."})
        self.emit("done", {})
        self.q.put(None)

    def events(self):
        while True:
            ev = self.q.get()
            if ev is None:
                return
            yield ev


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode())
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            return self._json(200, {"status": "ok"})
        if parsed.path == "/events":
            sid = parse_qs(parsed.query).get("session", [""])[0]
            session = _sessions.get(sid)
            if session is None:
                return self._json(404, {"error": "unknown session"})
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            for ev in session.events():
                try:
                    self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/run":
            task = self._body().get("task")
            if not task:
                return self._json(400, {"error": "missing 'task'"})
            session = MockSession(task).start()
            _sessions[session.id] = session
            return self._json(200, {"session_id": session.id})
        if parsed.path == "/approve":
            body = self._body()
            session = _sessions.get(body.get("session", ""))
            if session is None:
                return self._json(404, {"error": "unknown session"})
            ok = session.decide(body.get("id", ""), body.get("decision", "deny"))
            return self._json(200, {"ok": ok})
        self._json(404, {"error": "not found"})


def main() -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("[mock-daemon] listening on http://127.0.0.1:8765 (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
