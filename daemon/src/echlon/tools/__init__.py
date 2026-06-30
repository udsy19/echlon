"""Echlon tool layer. Tools use consistent prefixes (shell_, file_, todo_) so
later masking/gating is a simple name-prefix state machine (Manus lesson)."""

from __future__ import annotations

from pathlib import Path

from smolagents import Tool

from . import context
from .browser import (
    browser_click,
    browser_navigate,
    browser_read_text,
    browser_snapshot,
    browser_type,
)
from .computer import COMPUTER_TOOLS
from .files import file_edit, file_read, file_write
from .shell import shell_exec
from .todo import todo_read, todo_write


def build_tools(workspace: Path, os_control: bool = True) -> list[Tool]:
    """Initialize the workspace and return the active tool set.

    When os_control is True (default), the whole-desktop computer_* tools
    (screenshot + mouse/keyboard) are included alongside the shell/file/browser
    tools, so the agent can drive any app — not just the browser.
    """
    context.set_workspace(workspace)
    tools = [
        shell_exec,
        file_read,
        file_write,
        file_edit,
        todo_write,
        todo_read,
        browser_navigate,
        browser_snapshot,
        browser_click,
        browser_type,
        browser_read_text,
    ]
    if os_control:
        tools += COMPUTER_TOOLS
    return tools


__all__ = [
    "build_tools",
    "context",
    "shell_exec",
    "file_read",
    "file_write",
    "file_edit",
    "todo_write",
    "todo_read",
    "browser_navigate",
    "browser_snapshot",
    "browser_click",
    "browser_type",
    "browser_read_text",
    "COMPUTER_TOOLS",
]
