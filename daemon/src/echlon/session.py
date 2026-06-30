"""Session API — the programmatic, streaming interface the UI consumes (PLAN.md §4-5).

A Session runs one task on a background thread and emits structured Events onto a
queue: started / plan / tool_call / step / approval_request / final_answer /
error / done. The UI (or CLI) consumes events() and answers approval_request via
decide().

Approval bridge: the guardrail policy's prompter is pointed at this session, so a
risky action emits an approval_request event and blocks the agent thread until
the consumer calls decide() — turning the terminal y/n prompt into a UI round-trip.

Single active session per process: tools/policy/browser hold module-level state,
so one task runs at a time (the right model for a local single-user agent).
"""

from __future__ import annotations

import itertools
import queue
import threading
import uuid
from dataclasses import asdict, dataclass, field

from .agent import build_agent
from .config import EchlonConfig
from .logsetup import get_logger
from .policy import set_policy

log = get_logger(__name__)

_DECISIONS = {"once", "always", "deny"}


@dataclass
class Event:
    type: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class Session:
    def __init__(self, cfg: EchlonConfig, task: str, model=None, approval_timeout: float | None = None) -> None:
        self.cfg = cfg
        self.task = task
        self.id = uuid.uuid4().hex[:8]
        self.status = "pending"  # pending | running | done | error | cancelled
        self.result: object | None = None
        self.approval_timeout = approval_timeout
        self._model = model  # test injection
        self._agent = None
        self._cancelled = False
        self._log: list[Event] = []          # full buffer -> replay on reconnect
        self._cv = threading.Condition()
        self._finished = False
        self._approvals: dict[str, queue.Queue[str]] = {}
        self._ctr = itertools.count(1)
        self._thread: threading.Thread | None = None

    # --- approval bridge (runs on the agent thread) --------------------------

    def _prompter(self, summary: str) -> str:
        if self._cancelled:
            return "deny"
        aid = f"a{next(self._ctr)}"
        decision_q: queue.Queue[str] = queue.Queue()
        self._approvals[aid] = decision_q
        self._emit("approval_request", {"id": aid, "summary": summary})
        try:
            decision = decision_q.get(timeout=self.approval_timeout)
        except queue.Empty:
            self._emit("approval_timeout", {"id": aid, "summary": summary})
            decision = "deny"
        finally:
            self._approvals.pop(aid, None)
        return decision if decision in _DECISIONS else "deny"

    def decide(self, approval_id: str, decision: str) -> bool:
        """Answer a pending approval. Returns False if the id is unknown."""
        dq = self._approvals.get(approval_id)
        if dq is None:
            return False
        dq.put(decision)
        return True

    def cancel(self) -> bool:
        """Request graceful cancellation. Interrupts the agent loop and unblocks
        any pending approval (as a deny). Returns True if the session was running."""
        if self.status != "running":
            return False
        self._cancelled = True
        if self._agent is not None:
            try:
                self._agent.interrupt()
            except Exception:
                pass
        for dq in list(self._approvals.values()):
            dq.put("deny")
        return True

    # --- run / event stream --------------------------------------------------

    def _emit(self, type_: str, data: dict | None = None) -> None:
        with self._cv:
            self._log.append(Event(type_, data or {}))
            self._cv.notify_all()

    def start(self) -> "Session":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        from smolagents import AgentMaxStepsError

        from .tools import browser

        self.status = "running"
        try:
            self._agent = build_agent(self.cfg, model=self._model, stream_outputs=False)
            # Override the policy prompter so confirmations route to this session.
            set_policy(self.cfg.policy_mode, self.cfg.workspace, prompter=self._prompter)  # type: ignore[arg-type]
            self._emit("started", {"task": self.task, "model": self.cfg.model_id})
            log.info("session running", extra={"session": self.id, "model": self.cfg.model_id})
            for ev in self._agent.run(self.task, stream=True):
                self._translate(ev)
            self.status = "cancelled" if self._cancelled else "done"
        except AgentMaxStepsError as exc:
            self.status = "error"
            self._emit("error", {"message": f"max steps reached: {exc}", "kind": "max_steps"})
            log.warning("session max steps", extra={"session": self.id})
        except Exception as exc:  # noqa: BLE001 — surface to the consumer
            self.status = "cancelled" if self._cancelled else "error"
            self._emit("error", {"message": str(exc)})
            log.error("session failed", extra={"session": self.id, "error": str(exc)})
        finally:
            try:
                browser.reset()  # don't leak browser state into the next session
            except Exception:
                pass
            self._emit("done", {"status": self.status})
            log.info("session done", extra={"session": self.id, "status": self.status,
                                            "events": len(self._log)})
            with self._cv:
                self._finished = True
                self._cv.notify_all()

    def _translate(self, ev: object) -> None:
        name = type(ev).__name__
        if name == "ToolCall":
            self._emit("tool_call", {"name": ev.name, "arguments": str(ev.arguments)[:2000]})  # type: ignore[attr-defined]
        elif name == "ActionStep":
            self._emit(
                "step",
                {
                    "step": ev.step_number,  # type: ignore[attr-defined]
                    "observations": (ev.observations or "")[:4000],  # type: ignore[attr-defined]
                    "error": str(ev.error) if ev.error else None,  # type: ignore[attr-defined]
                },
            )
        elif name == "PlanningStep":
            self._emit("plan", {"plan": str(getattr(ev, "plan", ""))[:4000]})
        elif name == "FinalAnswerStep":
            self.result = ev.output  # type: ignore[attr-defined]
            self._emit("final_answer", {"output": str(ev.output)})  # type: ignore[attr-defined]

    def events(self, start: int = 0):
        """Yield Events from index `start` until the stream finishes (blocking).

        Buffered, so a reconnecting consumer can pass the count it already saw
        and get exactly the events it missed, then tail live ones — SSE has no
        replay of its own.
        """
        i = start
        while True:
            with self._cv:
                while i >= len(self._log) and not self._finished:
                    self._cv.wait()
                if i >= len(self._log) and self._finished:
                    return
                ev = self._log[i]
            i += 1
            yield ev

    def wait(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)
