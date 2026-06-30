"""Phase 2 context-engineering refinements: restorable truncation + recitation."""

from __future__ import annotations

from pathlib import Path

from echlon.agent import _recite_todo
from echlon.tools import context


def test_truncate_restorable_short_passthrough(tmp_path: Path) -> None:
    context.set_workspace(tmp_path)
    assert context.truncate_restorable("hello", 100) == "hello"


def test_truncate_restorable_saves_full(tmp_path: Path) -> None:
    context.set_workspace(tmp_path)
    big = "x" * 5000
    out = context.truncate_restorable(big, 1000, label="shell output")
    assert out.startswith("x" * 1000)
    assert "truncated at 1000" in out and "file_read" in out
    # The full content was saved to a real file that round-trips.
    saved = list((tmp_path / ".echlon" / "obs").glob("*.txt"))
    assert len(saved) == 1
    assert saved[0].read_text() == big
    assert str(saved[0]) in out


class _Step:
    def __init__(self, observations: str | None) -> None:
        self.observations = observations


def test_recite_appends_todo(tmp_path: Path) -> None:
    context.set_workspace(tmp_path)
    (tmp_path / "todo.md").write_text("- [x] step one\n- [ ] step two")
    step = _Step("Execution logs: ok")
    _recite_todo(step)
    assert "Execution logs: ok" in step.observations
    assert "[current plan — todo.md]" in step.observations
    assert "step two" in step.observations


def test_recite_noop_without_todo(tmp_path: Path) -> None:
    context.set_workspace(tmp_path)
    step = _Step("only obs")
    _recite_todo(step)
    assert step.observations == "only obs"  # unchanged when no todo.md
