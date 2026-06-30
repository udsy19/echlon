"""Session API: event streaming and the approval round-trip (offline)."""

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
    return EchlonConfig(provider="anthropic", workspace=tmp_path, policy_mode="ask", planning_interval=None)


def test_session_streams_to_final_answer(tmp_path: Path) -> None:
    model = FakeModel([
        "<code>\nprint(file_write(path='note.txt', content='hi'))\n</code>",
        "<code>\nfinal_answer('all done')\n</code>",
    ])
    s = Session(_cfg(tmp_path), "write note.txt then finish", model=model).start()

    types, final = [], None
    for ev in s.events():
        types.append(ev.type)
        if ev.type == "final_answer":
            final = ev.data["output"]

    assert "started" in types
    assert "final_answer" in types
    assert types[-1] == "done"
    assert final == "all done"
    assert (tmp_path / "note.txt").read_text() == "hi"


def test_session_approval_roundtrip_deny(tmp_path: Path) -> None:
    model = FakeModel([
        "<code>\nprint(shell_exec(command='rm -rf /tmp/echlon-approval-test'))\n</code>",
        "<code>\nfinal_answer('handled the block')\n</code>",
    ])
    s = Session(_cfg(tmp_path), "try a destructive command", model=model).start()

    saw_request = False
    blocked_in_obs = False
    for ev in s.events():
        if ev.type == "approval_request":
            saw_request = True
            assert s.decide(ev.data["id"], "deny")  # consumer denies
        if ev.type == "step" and "blocked" in (ev.data.get("observations") or ""):
            blocked_in_obs = True

    assert saw_request, "destructive shell should have requested approval"
    assert blocked_in_obs, "the model should have seen the block in an observation"
    assert s.result == "handled the block"
    assert s.status == "done"


def test_session_approval_timeout(tmp_path: Path) -> None:
    # No one answers the approval; it times out and is treated as deny.
    model = FakeModel([
        "<code>\nprint(shell_exec(command='rm -rf /tmp/echlon-timeout-test'))\n</code>",
        "<code>\nfinal_answer('done after timeout')\n</code>",
    ])
    s = Session(_cfg(tmp_path), "destructive then finish", model=model, approval_timeout=0.2).start()

    types = [ev.type for ev in s.events()]
    assert "approval_request" in types
    assert "approval_timeout" in types
    assert s.result == "done after timeout"
