"""Shared workspace context for tools.

Tools operate relative to a single workspace directory. We hold it in a module
global set once at session start, so the `@tool` functions stay plain (no
closures) and smolagents can introspect their signatures cleanly.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_workspace: Path = Path.cwd()


def set_workspace(path: Path) -> Path:
    """Set the active workspace directory, creating it if needed."""
    global _workspace
    _workspace = Path(path).expanduser().resolve()
    _workspace.mkdir(parents=True, exist_ok=True)
    return _workspace


def workspace() -> Path:
    """Return the active workspace directory."""
    return _workspace


def resolve(path: str) -> Path:
    """Resolve a tool-supplied path against the workspace.

    Absolute paths are honored as-is (full host access — see PLAN.md §1);
    relative paths are taken under the workspace root.
    """
    p = Path(path).expanduser()
    return p if p.is_absolute() else (_workspace / p)


def truncate_restorable(text: str, limit: int, label: str = "output") -> str:
    """Cap an observation but keep it *restorable* (Manus lesson: compression
    must lose nothing). Oversized text is saved to a file under the workspace and
    the path is included so the agent can file_read the full content on demand.
    """
    if len(text) <= limit:
        return text
    obs_dir = _workspace / ".echlon" / "obs"
    obs_dir.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12] + ".txt"
    path = obs_dir / name
    path.write_text(text, encoding="utf-8")
    return (
        text[:limit]
        + f"\n... [{label} truncated at {limit} chars — full {len(text)} chars saved to "
        + f"{path}; use file_read to see the rest]"
    )
