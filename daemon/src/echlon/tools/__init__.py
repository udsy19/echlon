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
from .connectors import CONNECTOR_TOOLS, load_mcp_tools, set_connectors_file
from .files import file_edit, file_read, file_write
from .shell import shell_exec
from .skills import SKILL_TOOLS, set_skills_dir
from .todo import todo_read, todo_write


def build_tools(
    workspace: Path,
    os_control: bool = True,
    skills_dir: Path | None = None,
    connectors_file: Path | None = None,
) -> list[Tool]:
    """Initialize the workspace and return the active tool set.

    When os_control is True (default), the whole-desktop computer_* tools are
    included. When skills_dir is given, the skill-acquisition tools are included.
    When connectors_file is given, the connector-management tools are included and
    enabled MCP connectors are loaded (best-effort) and their tools merged in.
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
    if skills_dir is not None:
        set_skills_dir(skills_dir)
        tools += SKILL_TOOLS
    if connectors_file is not None:
        set_connectors_file(connectors_file)
        tools += CONNECTOR_TOOLS
        tools += load_mcp_tools()  # enabled connectors' tools (best-effort)
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
