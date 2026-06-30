"""Conversational Session: turns, steering, approvals, replay (offline)."""

from __future__ import annotations

from pathlib import Path

from smolagents.models import ChatMessage, TokenUsage

from echlon.config import EchlonConfig
from echlon.session import Session


class FakeModel:
    def __init__(self, steps: list[str]) -> None:
        self._steps = steps
        self._i = 0

    def generate(self, messages, **kwargs) -> ChatMessage:
        content = self._steps[min(self._i, len(self._steps) - 1)]
        self._i += 1
        return ChatMessage(role="assistant", content=content, tool_calls=None, raw={},
                           token_usage=TokenUsage(input_tokens=0, output_tokens=0))


def _cfg(tmp_path: Path) -> EchlonConfig:
    return EchlonConfig(provider="anthropic", workspace=tmp_path, policy_mode="ask",
                        planning_interval=None, os_control=False,
                        skills_dir=tmp_path / "skills")


def _collect_until(session: Session, stop_type: str, start: int = 0, on=None) -> list:
    """Tail the live event stream from `start` up to and including the first
    event of `stop_type`."""
    out = []
    for ev in session.events(start):
        if on:
            on(ev)
        out.append(ev)
        if ev.type == stop_type:
            break
    return out


def test_turn_runs_to_final_answer(tmp_path: Path) -> None:
    model = FakeModel([
        "<code>\nprint(file_write(path='note.txt', content='hi'))\n</code>",
        "<code>\nfinal_answer('all done')\n</code>",
    ])
    s = Session(_cfg(tmp_path), model=model)
    s.send("write note.txt then finish")

    evs = _collect_until(s, "turn_done")
    types = [e.type for e in evs]

    assert "started" in types and "turn_started" in types
    assert "final_answer" in types
    assert types[-1] == "turn_done"
    final = next(e for e in evs if e.type == "final_answer").data["output"]
    assert final == "all done"
    assert (tmp_path / "note.txt").read_text() == "hi"
    s.close()


def test_steer_message_injected_into_step(tmp_path: Path) -> None:
    # The steer drain folds queued user messages into the step's observations.
    s = Session(_cfg(tmp_path), model=FakeModel(["<code>\nfinal_answer('x')\n</code>"]))
    s._steer.put("actually, use uppercase")

    class _Step:
        observations = "original obs"

    step = _Step()
    s._drain_steer(step)
    assert "actually, use uppercase" in step.observations
    assert "original obs" in step.observations  # appended, not replaced


def test_send_while_running_queues_steer(tmp_path: Path) -> None:
    s = Session(_cfg(tmp_path), model=FakeModel(["<code>\nfinal_answer('x')\n</code>"]))
    s.status = "running"  # simulate a turn in progress
    result = s.send("change of plans")
    assert result["mode"] == "steer"
    assert s._steer.get_nowait() == "change of plans"
    assert any(e.type == "user_message" for e in s._log)  # surfaced in the thread


def test_multi_turn_retains_session(tmp_path: Path) -> None:
    model = FakeModel([
        "<code>\nfinal_answer('one')\n</code>",
        "<code>\nfinal_answer('two')\n</code>",
    ])
    s = Session(_cfg(tmp_path), model=model)
    s.send("first task")
    s.wait()
    offset = len(s._log)
    s.send("second task")
    s.wait()
    s.close()

    turn2 = [e.type for e in s.events(offset)]
    assert "turn_started" in turn2 and "final_answer" in turn2
    assert s.result == "two"  # second turn's answer; memory was continued


def test_approval_roundtrip_deny(tmp_path: Path) -> None:
    model = FakeModel([
        "<code>\nprint(shell_exec(command='rm -rf /tmp/echlon-approval-test'))\n</code>",
        "<code>\nfinal_answer('handled the block')\n</code>",
    ])
    s = Session(_cfg(tmp_path), model=model)
    s.send("try a destructive command")

    saw_request = blocked = False

    def watch(ev):
        nonlocal saw_request, blocked
        if ev.type == "approval_request":
            saw_request = True
            s.decide(ev.data["id"], "deny")
        if ev.type == "step" and "blocked" in (ev.data.get("observations") or ""):
            blocked = True

    _collect_until(s, "turn_done", on=watch)
    assert saw_request and blocked
    assert s.result == "handled the block"
    s.close()


def test_event_replay(tmp_path: Path) -> None:
    model = FakeModel([
        "<code>\nprint(file_write(path='r.txt', content='x'))\n</code>",
        "<code>\nfinal_answer('ok')\n</code>",
    ])
    s = Session(_cfg(tmp_path), model=model)
    s.send("write then finish")
    s.wait()
    s.close()

    full = [e.type for e in s.events(0)]
    partial = [e.type for e in s.events(2)]
    assert full[0] == "user_message" and "started" in full and "closed" in full
    assert partial == full[2:]


def test_approval_timeout(tmp_path: Path) -> None:
    model = FakeModel([
        "<code>\nprint(shell_exec(command='rm -rf /tmp/echlon-timeout-test'))\n</code>",
        "<code>\nfinal_answer('done after timeout')\n</code>",
    ])
    s = Session(_cfg(tmp_path), model=model, approval_timeout=0.2)
    s.send("destructive then finish")

    types = [e.type for e in _collect_until(s, "turn_done")]
    assert "approval_request" in types and "approval_timeout" in types
    assert s.result == "done after timeout"
    s.close()


def test_close_ends_stream(tmp_path: Path) -> None:
    s = Session(_cfg(tmp_path), model=FakeModel(["<code>\nfinal_answer('x')\n</code>"]))
    s.close()
    # After close the stream is finished, so events() returns rather than blocking.
    assert [e.type for e in s.events(0)][-1] == "closed"
