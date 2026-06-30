"""Filesystem tools — also the agent's externalized memory store (PLAN.md §2)."""

from __future__ import annotations

from smolagents import tool

from ..policy import policy
from . import context


@tool
def file_read(path: str) -> str:
    """Read a UTF-8 text file and return its contents.

    Args:
        path: File path, relative to the workspace or absolute.
    """
    p = context.resolve(path)
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"[error] no such file: {p}"
    except UnicodeDecodeError:
        return f"[error] not a UTF-8 text file: {p}"


@tool
def file_write(path: str, content: str) -> str:
    """Create or overwrite a text file with the given content.

    Parent directories are created automatically.

    Args:
        path: File path, relative to the workspace or absolute.
        content: Full text content to write.
    """
    p = context.resolve(path)
    decision = policy().guard_write(p)
    if not decision.allowed:
        return decision.message
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"[ok] wrote {len(content)} chars to {p}"


@tool
def file_edit(path: str, old: str, new: str) -> str:
    """Replace the first exact occurrence of `old` with `new` in a file.

    Fails if `old` is absent or appears more than once, so edits are unambiguous.

    Args:
        path: File path, relative to the workspace or absolute.
        old: Exact text to find. Must occur exactly once.
        new: Replacement text.
    """
    p = context.resolve(path)
    decision = policy().guard_write(p)
    if not decision.allowed:
        return decision.message
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"[error] no such file: {p}"

    count = text.count(old)
    if count == 0:
        return f"[error] `old` text not found in {p}"
    if count > 1:
        return f"[error] `old` text occurs {count} times in {p}; make it unique"

    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    return f"[ok] edited {p}"
