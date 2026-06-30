"""Shell execution tool (runs on the host — full host access per PLAN.md §1)."""

from __future__ import annotations

import subprocess

from smolagents import tool

from ..policy import policy
from . import context


@tool
def shell_exec(command: str, timeout: int = 120) -> str:
    """Run a shell command on the host machine and return its output.

    The command runs in the workspace directory. Combined stdout and stderr are
    returned along with the exit code. Errors are returned as text (not hidden)
    so you can see what failed and adapt.

    Args:
        command: The shell command to execute.
        timeout: Maximum seconds to allow the command to run before killing it.
    """
    decision = policy().guard_shell(command)
    if not decision.allowed:
        return decision.message
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(context.workspace()),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"[error] command timed out after {timeout}s: {command}"

    output = ((result.stdout or "") + (result.stderr or "")).strip()
    header = f"[exit {result.returncode}]"
    if not output:
        return f"{header} (no output)"
    return f"{header}\n{context.truncate_restorable(output, 8000, label='shell output')}"
