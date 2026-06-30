"""Guardrail policy: classification, modes, consent, and tool integration."""

from __future__ import annotations

from pathlib import Path

from echlon import policy as pol
from echlon.policy import Policy
from echlon.tools import build_tools
from echlon.tools.files import file_write
from echlon.tools.shell import shell_exec


def _const(choice: str):
    return lambda summary: choice


def test_permissive_allows_destructive(tmp_path) -> None:
    p = Policy(mode="permissive", workspace=tmp_path, prompter=_const("deny"))
    assert p.guard_shell("rm -rf /").allowed


def test_ask_allows_safe_shell(tmp_path) -> None:
    # prompter raises if consulted — proves safe commands don't prompt
    p = Policy(mode="ask", workspace=tmp_path, prompter=lambda s: (_ for _ in ()).throw(AssertionError("prompted")))
    assert p.guard_shell("ls -la").allowed


def test_ask_blocks_destructive_on_deny(tmp_path) -> None:
    p = Policy(mode="ask", workspace=tmp_path, prompter=_const("deny"))
    d = p.guard_shell("rm -rf build")
    assert not d.allowed and "blocked" in d.message


def test_ask_allows_destructive_on_once(tmp_path) -> None:
    p = Policy(mode="ask", workspace=tmp_path, prompter=_const("once"))
    assert p.guard_shell("sudo reboot").allowed


def test_always_remembers(tmp_path) -> None:
    calls = {"n": 0}

    def once_then_boom(summary: str) -> str:
        calls["n"] += 1
        if calls["n"] > 1:
            raise AssertionError("prompted twice for an 'always' action")
        return "always"

    p = Policy(mode="ask", workspace=tmp_path, prompter=once_then_boom)
    assert p.guard_shell("rm -rf x").allowed
    assert p.guard_shell("rm -rf x").allowed  # remembered, no second prompt


def test_write_inside_workspace_allowed(tmp_path) -> None:
    p = Policy(mode="ask", workspace=tmp_path, prompter=_const("deny"))
    assert p.guard_write(tmp_path / "sub" / "a.txt").allowed


def test_write_outside_workspace_blocked(tmp_path) -> None:
    p = Policy(mode="ask", workspace=tmp_path, prompter=_const("deny"))
    d = p.guard_write(tmp_path.parent / "escape.txt")
    assert not d.allowed


def test_strict_prompts_every_shell(tmp_path) -> None:
    p = Policy(mode="strict", workspace=tmp_path, prompter=_const("deny"))
    assert not p.guard_shell("ls").allowed  # even a safe command is gated


def test_noninteractive_blocks_with_hint(tmp_path) -> None:
    # No prompter + non-tty (pytest) -> risky action is blocked with guidance.
    p = Policy(mode="ask", workspace=tmp_path, prompter=None)
    d = p.guard_shell("rm -rf /")
    assert not d.allowed and "--allow-all" in d.message


# --- integration through the actual tools ---------------------------------

def test_tool_shell_blocked(tmp_path) -> None:
    build_tools(tmp_path)
    pol.set_policy("ask", tmp_path, prompter=_const("deny"))
    out = shell_exec("rm -rf important")
    assert "blocked" in out


def test_tool_write_outside_blocked(tmp_path) -> None:
    build_tools(tmp_path)
    pol.set_policy("ask", tmp_path, prompter=_const("deny"))
    out = file_write(str(tmp_path.parent / "escape.txt"), "x")
    assert "blocked" in out
    assert not (tmp_path.parent / "escape.txt").exists()
