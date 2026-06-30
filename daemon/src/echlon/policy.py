"""Guardrail / consent layer — the safety valve for full host access (PLAN.md §1, §4).

Risky tool actions (destructive shell commands, writes outside the workspace)
are routed through a Policy that decides allow / ask / deny. Modes:

  permissive  allow everything (the "dial it off" setting; --allow-all)
  ask         (default) auto-allow safe + in-workspace actions; confirm risky ones
  strict      ask on every shell command and every out-of-workspace write

A denial returns a string the model sees, so it adapts rather than crashing
(keep-errors-visible). This module imports nothing from `tools` (no cycle); the
workspace root is supplied at session start via set_policy().
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

Mode = Literal["permissive", "ask", "strict"]

# Commands that are hard to reverse or system-wide. Pattern match is a heuristic
# tripwire, not a sandbox — the real isolation story is Phase 6.
_DESTRUCTIVE = [
    re.compile(r"\brm\s+(-\w*\s+)*-\w*[rf]", re.I),   # rm -rf / -fr / -r -f
    re.compile(r"\bsudo\b", re.I),
    re.compile(r"\bmkfs\b", re.I),
    re.compile(r"\bdd\s+.*\bof=", re.I),
    re.compile(r">\s*/dev/", re.I),
    re.compile(r"\b(shutdown|reboot|halt)\b", re.I),
    re.compile(r"\b(kill(all)?|pkill)\b", re.I),
    re.compile(r"\bchmod\s+-R\s+777\b", re.I),
    re.compile(r"git\s+push\s+.*--force", re.I),
    re.compile(r"(curl|wget)\b.*\|\s*(sudo\s+)?(ba)?sh", re.I),  # curl ... | sh
    re.compile(r":\(\)\s*\{", re.I),                  # fork bomb
]


@dataclass
class Decision:
    allowed: bool
    message: str = ""


def _terminal_prompter(summary: str) -> str:
    """Ask the user at the terminal. Returns 'once' | 'always' | 'deny'."""
    print(f"\n[echlon] ⚠ risky action requested:\n    {summary}", file=sys.stderr)
    try:
        ans = input("    allow? [o]nce / [a]lways / [d]eny: ").strip().lower()
    except EOFError:
        return "deny"
    if ans in ("o", "once", "y", "yes"):
        return "once"
    if ans in ("a", "always"):
        return "always"
    return "deny"


@dataclass
class Policy:
    mode: Mode = "ask"
    workspace: Path = field(default_factory=Path.cwd)
    prompter: Callable[[str], str] | None = None  # None -> terminal (if tty)
    _always: set[str] = field(default_factory=set)

    # --- public guards (called by tools) -------------------------------------

    def guard_shell(self, command: str) -> Decision:
        if self.mode == "permissive":
            return Decision(True)
        risky = self.mode == "strict" or self._is_destructive(command)
        if not risky:
            return Decision(True)
        return self._confirm(f"shell: {command}")

    def guard_write(self, resolved_path: Path) -> Decision:
        if self.mode == "permissive":
            return Decision(True)
        outside = not self._within_workspace(resolved_path)
        if not outside:
            return Decision(True)
        return self._confirm(f"write outside workspace: {resolved_path}")

    # --- internals -----------------------------------------------------------

    def _is_destructive(self, command: str) -> bool:
        return any(p.search(command) for p in _DESTRUCTIVE)

    def _within_workspace(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.workspace.resolve())
            return True
        except ValueError:
            return False

    def _confirm(self, summary: str) -> Decision:
        if summary in self._always:
            return Decision(True)
        prompter = self.prompter or (_terminal_prompter if sys.stdin.isatty() else None)
        if prompter is None:
            return Decision(
                False,
                f"[blocked] risky action requires confirmation but the session is "
                f"non-interactive: {summary}. Re-run with --allow-all to permit, or "
                f"choose a safe alternative.",
            )
        choice = prompter(summary)
        if choice == "always":
            self._always.add(summary)
            return Decision(True)
        if choice == "once":
            return Decision(True)
        return Decision(False, f"[blocked by user] {summary}")


_policy = Policy()


def set_policy(mode: Mode, workspace: Path, prompter: Callable[[str], str] | None = None) -> Policy:
    """Install the active policy for this session."""
    global _policy
    _policy = Policy(mode=mode, workspace=Path(workspace).resolve(), prompter=prompter)
    return _policy


def policy() -> Policy:
    return _policy
