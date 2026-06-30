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
from .policy import set_policy

_DECISIONS = {"once", "always", "deny"}


@dataclass
class Event:
    type: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class Session:
    def __init__(self, cfg: EchlonConfig, task: str, model=None) -> None:
        self.cfg = cfg
        self.task = task
        self.id = uuid.uuid4().hex[:8]
        self.result: object | None = None
        self._model = model  # test injection
        self._q: queue.Queue[Event | None] = queue.Queue()
        self._approvals: dict[str, queue.Queue[str]] = {}
        self._ctr = itertools.count(1)
        self._thread: threading.Thread | None = None

    # --- approval bridge (runs on the agent thread) --------------------------

    def _prompter(self, summary: str) -> str:
        aid = f"a{next(self._ctr)}"
        decision_q: queue.Queue[str] = queue.Queue()
        self._approvals[aid] = decision_q
        self._emit("approval_request", {"id": aid, "summary": summary})
        decision = decision_q.get()  # blocks the agent until the consumer decides
        self._approvals.pop(aid, None)
        return decision if decision in _DECISIONS else "deny"

    def decide(self, approval_id: str, decision: str) -> bool:
        """Answer a pending approval. Returns False if the id is unknown."""
        dq = self._approvals.get(approval_id)
        if dq is None:
            return False
        dq.put(decision)
        return True

    # --- run / event stream --------------------------------------------------

    def _emit(self, type_: str, data: dict | None = None) -> None:
        self._q.put(Event(type_, data or {}))

    def start(self) -> "Session":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        try:
            agent = build_agent(self.cfg, model=self._model, stream_outputs=False)
            # Override the policy prompter so confirmations route to this session.
            set_policy(self.cfg.policy_mode, self.cfg.workspace, prompter=self._prompter)  # type: ignore[arg-type]
            self._emit("started", {"task": self.task, "model": self.cfg.model_id})
            for ev in agent.run(self.task, stream=True):
                self._translate(ev)
        except Exception as exc:  # noqa: BLE001 — surface to the consumer
            self._emit("error", {"message": str(exc)})
        finally:
            self._emit("done", {})
            self._q.put(None)  # end-of-stream sentinel

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

    def events(self):
        """Yield Events until the end-of-stream sentinel (blocking)."""
        while True:
            ev = self._q.get()
            if ev is None:
                return
            yield ev

    def wait(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)
