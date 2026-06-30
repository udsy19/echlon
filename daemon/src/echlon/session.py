"""Conversational Session — the multi-turn, steer-able interface the UI consumes.

A Session is one ongoing conversation with the agent. You `send()` messages:
  - when the agent is idle, a message starts a new turn (agent.run continuing the
    same memory, so context carries across turns);
  - when the agent is mid-turn, the message is queued and drained into the next
    step's observations (turn-based steering — the agent adapts at its next step).

The session stays alive across turns and emits a single, append-only event stream
(started/turn_started/user_message/plan/tool_call/step/approval_request/
approval_timeout/final_answer/turn_done/error/closed). `events(start)` replays
from any offset and tails live events until the session is `close()`d.

Approval bridge: the guardrail policy's prompter routes to this session, so a
risky action emits approval_request and blocks the turn thread until decide().

Single open session per process (tools/policy/browser hold module-level state):
one conversation at a time, which fits a local single-user agent. Browser state
persists across turns and is reset on close.
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
    def __init__(self, cfg: EchlonConfig, model=None, approval_timeout: float | None = None) -> None:
        self.cfg = cfg
        self.id = uuid.uuid4().hex[:8]
        self.status = "idle"  # idle | running | closed
        self.result: object | None = None
        self.approval_timeout = approval_timeout
        self._model = model  # test injection
        self._agent = None
        self._turn = 0
        self._cancelled_turn = False
        self._closed = False
        self._log: list[Event] = []
        self._cv = threading.Condition()
        self._finished = False  # set only on close → ends event streams
        self._approvals: dict[str, queue.Queue[str]] = {}
        self._ctr = itertools.count(1)
        self._steer: queue.Queue[str] = queue.Queue()  # mid-turn user messages
        self._turn_thread: threading.Thread | None = None

    # --- agent + steering ----------------------------------------------------

    def _ensure_agent(self):
        if self._agent is None:
            self._agent = build_agent(
                self.cfg, model=self._model, stream_outputs=False,
                extra_callbacks=[self._drain_steer],
            )
            # Route guardrail confirmations to this session.
            set_policy(self.cfg.policy_mode, self.cfg.workspace, prompter=self._prompter)  # type: ignore[arg-type]
        return self._agent

    def _drain_steer(self, step, agent=None) -> None:
        """Step callback: fold any queued user messages into this step so the
        agent sees them on its next reasoning pass (turn-based steering)."""
        msgs = []
        while True:
            try:
                msgs.append(self._steer.get_nowait())
            except queue.Empty:
                break
        if msgs:
            note = "\n\n[user message — incorporate this into your plan now]\n" + "\n".join(msgs)
            existing = getattr(step, "observations", None)
            step.observations = (existing + note) if existing else note.strip()

    # --- approval bridge (runs on the turn thread) ---------------------------

    def _prompter(self, summary: str) -> str:
        if self._cancelled_turn or self._closed:
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
        dq = self._approvals.get(approval_id)
        if dq is None:
            return False
        dq.put(decision)
        return True

    # --- messaging / turns ---------------------------------------------------

    def send(self, text: str) -> dict:
        """Send a message. Starts a new turn if idle, else steers the running turn."""
        if self._closed:
            return {"ok": False, "reason": "session closed"}
        if not text or not isinstance(text, str):
            return {"ok": False, "reason": "empty message"}
        self._emit("user_message", {"text": text})
        if self.status == "running":
            self._steer.put(text)
            log.info("steer queued", extra={"session": self.id})
            return {"ok": True, "mode": "steer"}
        self._turn_thread = threading.Thread(target=self._run_turn, args=(text,), daemon=True)
        self._turn_thread.start()
        return {"ok": True, "mode": "turn"}

    def _run_turn(self, text: str) -> None:
        from smolagents import AgentMaxStepsError

        self.status = "running"
        self._cancelled_turn = False
        is_first = self._turn == 0
        if is_first:
            self._emit("started", {"task": text, "model": self.cfg.model_id})
        self._emit("turn_started", {"turn": self._turn + 1, "text": text})
        log.info("turn running", extra={"session": self.id, "turn": self._turn + 1})
        try:
            agent = self._ensure_agent()
            for ev in agent.run(text, reset=is_first, stream=True):
                self._translate(ev)
        except AgentMaxStepsError as exc:
            self._emit("error", {"message": f"max steps reached: {exc}", "kind": "max_steps"})
            log.warning("turn max steps", extra={"session": self.id})
        except Exception as exc:  # noqa: BLE001 — surface to the consumer
            self._emit("error", {"message": str(exc)})
            log.error("turn failed", extra={"session": self.id, "error": str(exc)})
        finally:
            self._turn += 1
            self._emit("turn_done", {"turn": self._turn,
                                     "status": "cancelled" if self._cancelled_turn else "ok"})
            if self._closed:
                self._finalize()
            else:
                self.status = "idle"

    def cancel(self) -> bool:
        """Cancel the in-progress turn (the session stays open and idle)."""
        if self.status != "running":
            return False
        self._cancelled_turn = True
        if self._agent is not None:
            try:
                self._agent.interrupt()
            except Exception:
                pass
        for dq in list(self._approvals.values()):
            dq.put("deny")
        return True

    def close(self) -> bool:
        """End the conversation: stop any running turn, reset the browser, end streams."""
        if self._closed:
            return False
        self._closed = True
        if self.status == "running":
            self.cancel()  # the turn thread will _finalize() when it unwinds
        else:
            self._finalize()
        return True

    def _finalize(self) -> None:
        try:
            from .tools import browser
            browser.reset()  # release browser only when the conversation ends
        except Exception:
            pass
        self.status = "closed"
        self._emit("closed", {"turns": self._turn})
        log.info("session closed", extra={"session": self.id, "turns": self._turn})
        with self._cv:
            self._finished = True
            self._cv.notify_all()

    # --- event stream --------------------------------------------------------

    def _emit(self, type_: str, data: dict | None = None) -> None:
        with self._cv:
            self._log.append(Event(type_, data or {}))
            self._cv.notify_all()

    def _translate(self, ev: object) -> None:
        name = type(ev).__name__
        if name == "ToolCall":
            self._emit("tool_call", {"name": ev.name, "arguments": str(ev.arguments)[:2000]})  # type: ignore[attr-defined]
        elif name == "ActionStep":
            self._emit("step", {
                "step": ev.step_number,  # type: ignore[attr-defined]
                "observations": (ev.observations or "")[:4000],  # type: ignore[attr-defined]
                "error": str(ev.error) if ev.error else None,  # type: ignore[attr-defined]
            })
        elif name == "PlanningStep":
            self._emit("plan", {"plan": str(getattr(ev, "plan", ""))[:4000]})
        elif name == "FinalAnswerStep":
            self.result = ev.output  # type: ignore[attr-defined]
            self._emit("final_answer", {"output": str(ev.output)})  # type: ignore[attr-defined]

    def events(self, start: int = 0):
        """Yield Events from index `start` until the session is closed (blocking)."""
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
        if self._turn_thread is not None:
            self._turn_thread.join(timeout)
