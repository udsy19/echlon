"""Echlon tool layer. Tools use consistent prefixes (shell_, file_, todo_) so
later masking/gating is a simple name-prefix state machine (Manus lesson)."""

from __future__ import annotations

from pathlib import Path

from smolagents import Tool

from . import context
from .files import file_edit, file_read, file_write
from .shell import shell_exec
from .todo import todo_read, todo_write


def build_tools(workspace: Path) -> list[Tool]:
    """Initialize the workspace and return the active tool set."""
    context.set_workspace(workspace)
    return [shell_exec, file_read, file_write, file_edit, todo_write, todo_read]


__all__ = [
    "build_tools",
    "context",
    "shell_exec",
    "file_read",
    "file_write",
    "file_edit",
    "todo_write",
    "todo_read",
]
