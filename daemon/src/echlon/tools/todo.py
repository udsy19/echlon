"""Task-plan recitation tools (Manus lesson: recite todo.md — PLAN.md §2).

Keeping a continually-rewritten todo.md re-injects the current objective at the
end of context every step, fighting drift on long tasks. Full auto-recitation
(re-injecting todo.md into context each step without a tool call) lands in
Phase 2; for now these tools plus the system instructions provide it.
"""

from __future__ import annotations

from smolagents import tool

from . import context

_TODO_FILE = "todo.md"


@tool
def todo_write(content: str) -> str:
    """Overwrite the task plan checklist (todo.md) in the workspace.

    Write the full plan up front, then rewrite it each step — checking off
    completed items and adding new ones — so the current objective stays in view.

    Args:
        content: The full markdown content of the todo list.
    """
    p = context.workspace() / _TODO_FILE
    p.write_text(content, encoding="utf-8")
    return f"[ok] updated {_TODO_FILE}"


@tool
def todo_read() -> str:
    """Read the current task plan (todo.md)."""
    p = context.workspace() / _TODO_FILE
    if not p.exists():
        return "[empty] no todo.md yet — write one with todo_write."
    return p.read_text(encoding="utf-8")
