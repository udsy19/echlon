"""Skill acquisition + loading — the capability-acquisition engine.

Skills follow the skills.sh / Agent-Skills format: a directory containing a
``SKILL.md`` with YAML frontmatter (``name``, ``description``) and a markdown
instruction body, plus optional scripts/resources. The agent acquires what it
doesn't know how to do: it installs a skill from GitHub (skills.sh aggregates
these repos), then loads the full instructions on demand — progressive
disclosure, so only metadata sits in context until a skill is actually used.

This is what lets "AI for everything" scale without hand-coding every vertical:
PowerPoint, video, research, etc. become skills the agent fetches itself.

Layout: ``<skills_dir>/<name>/SKILL.md``. Set once per session via
``set_skills_dir``; the tools read that module global so the @tool functions stay
plain (same pattern as tools/context.py).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from smolagents import tool

_skills_dir: Path = Path.home() / "echlon" / "skills"
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_KV = re.compile(r"\s*([A-Za-z_][\w.]*)\s*:\s*(.*?)\s*$")


def set_skills_dir(path: Path) -> Path:
    global _skills_dir
    _skills_dir = Path(path).expanduser().resolve()
    _skills_dir.mkdir(parents=True, exist_ok=True)
    return _skills_dir


def skills_dir() -> Path:
    return _skills_dir


def _parse_frontmatter(text: str) -> dict[str, str]:
    m = _FRONTMATTER.match(text)
    meta: dict[str, str] = {}
    if not m:
        return meta
    for line in m.group(1).splitlines():
        kv = _KV.match(line)
        if kv:
            meta[kv.group(1)] = kv.group(2).strip().strip('"').strip("'")
    return meta


def _installed() -> list[tuple[str, dict[str, str], Path]]:
    """(name, metadata, skill_dir) for every installed skill, sorted by name."""
    if not _skills_dir.exists():
        return []
    out = []
    for skill_md in sorted(_skills_dir.glob("*/SKILL.md")):
        meta = _parse_frontmatter(skill_md.read_text(encoding="utf-8", errors="replace"))
        out.append((meta.get("name") or skill_md.parent.name, meta, skill_md.parent))
    return out


def list_installed() -> list[dict[str, str]]:
    """[{name, description}] for the daemon's /skills endpoint."""
    return [{"name": name, "description": meta.get("description", "")} for name, meta, _ in _installed()]


def index_text() -> str:
    """One-line-per-skill index for the system prompt (metadata only)."""
    skills = _installed()
    if not skills:
        return ("No skills installed yet. If a task needs specialized know-how you don't have, "
                "find one at https://skills.sh and call skill_install('owner/repo').")
    lines = [f"- {name}: {meta.get('description', '(no description)')}" for name, meta, _ in skills]
    return "Installed skills (call skill_read('<name>') to load a skill's full instructions):\n" + "\n".join(lines)


def _normalize_source(source: str) -> str:
    """owner/repo -> https GitHub URL; pass URLs/git refs through unchanged."""
    s = source.strip()
    if s.startswith(("http://", "https://", "git@")):
        return s
    if re.fullmatch(r"[\w.-]+/[\w.-]+", s):
        return f"https://github.com/{s}"
    return s


@tool
def skill_list() -> str:
    """List the skills you currently have installed (names + descriptions).

    Call this when starting a task to see what specialized capabilities you
    already have before doing it from scratch.
    """
    return index_text()


@tool
def skill_read(name: str) -> str:
    """Load a skill's full instructions so you can follow them.

    Args:
        name: The skill name as shown by skill_list.
    """
    skill = _skills_dir / name
    md = skill / "SKILL.md"
    if not md.exists():
        return f"[error] no skill named {name!r}. Call skill_list() to see what's installed."
    body = md.read_text(encoding="utf-8", errors="replace")
    extras = [p.name for p in skill.iterdir() if p.name != "SKILL.md"]
    note = f"\n\n[bundled skill files in {skill}: {', '.join(extras)}]" if extras else ""
    return body[:12000] + note


@tool
def skill_install(source: str) -> str:
    """Acquire a new skill from a GitHub repo (skills.sh-compatible) or local path.

    Use this when you lack the know-how for a task: search https://skills.sh, then
    install the matching skill here. After installing, call skill_read on it and
    follow its instructions. Skill scripts run under the same guardrail as any
    other command.

    Args:
        source: 'owner/repo', a GitHub/GitLab URL, a git URL, or a local directory
            path containing one or more SKILL.md files.
    """
    dest_root = _skills_dir
    dest_root.mkdir(parents=True, exist_ok=True)

    local = Path(source).expanduser()
    tmp: tempfile.TemporaryDirectory | None = None
    try:
        if local.is_dir():
            repo = local
        else:
            tmp = tempfile.TemporaryDirectory()
            repo = Path(tmp.name) / "repo"
            r = subprocess.run(
                ["git", "clone", "--depth", "1", _normalize_source(source), str(repo)],
                capture_output=True, text=True, timeout=120,
            )
            if r.returncode != 0:
                return f"[error] could not fetch {source}: {(r.stderr or r.stdout).strip()[:300]}"

        found = [p for p in repo.rglob("SKILL.md") if len(p.relative_to(repo).parts) <= 4]
        if not found:
            return f"[error] no SKILL.md found in {source}."

        installed = []
        for skill_md in found:
            meta = _parse_frontmatter(skill_md.read_text(encoding="utf-8", errors="replace"))
            name = meta.get("name") or skill_md.parent.name
            target = dest_root / name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(skill_md.parent, target)
            installed.append(name)
    finally:
        if tmp is not None:
            tmp.cleanup()

    return (f"[ok] installed skill(s): {', '.join(installed)} into {dest_root}. "
            f"Call skill_read('{installed[0]}') to load it.")


SKILL_TOOLS = [skill_list, skill_read, skill_install]
