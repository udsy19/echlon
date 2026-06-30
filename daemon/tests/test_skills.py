"""Skill-acquisition engine: install (local), list, read, wiring."""

from __future__ import annotations

from pathlib import Path

from echlon.tools import build_tools, skills

SKILL_MD = """---
name: pptx-maker
description: Create PowerPoint decks from an outline.
---
# PPTX Maker
Build a deck.
"""


def _skill_repo(tmp_path: Path, name: str = "pptx-maker", body: str = SKILL_MD) -> Path:
    d = tmp_path / "repo" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body)
    return tmp_path / "repo"


def test_parse_frontmatter() -> None:
    meta = skills._parse_frontmatter(SKILL_MD)
    assert meta["name"] == "pptx-maker"
    assert "PowerPoint" in meta["description"]


def test_normalize_source() -> None:
    assert skills._normalize_source("owner/repo") == "https://github.com/owner/repo"
    assert skills._normalize_source("https://github.com/a/b") == "https://github.com/a/b"
    assert skills._normalize_source("git@github.com:a/b.git") == "git@github.com:a/b.git"


def test_install_from_local_then_list_and_read(tmp_path: Path) -> None:
    skills.set_skills_dir(tmp_path / "skills")
    out = skills.skill_install(str(_skill_repo(tmp_path)))
    assert "pptx-maker" in out
    assert (tmp_path / "skills" / "pptx-maker" / "SKILL.md").exists()

    index = skills.skill_list()
    assert "pptx-maker" in index and "PowerPoint" in index

    body = skills.skill_read("pptx-maker")
    assert "PPTX Maker" in body


def test_install_finds_nested_skill(tmp_path: Path) -> None:
    # skills.sh repos often nest skills at skills/<name>/SKILL.md
    nested = tmp_path / "repo" / "skills" / "deep"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text(SKILL_MD)
    skills.set_skills_dir(tmp_path / "skills")
    assert "pptx-maker" in skills.skill_install(str(tmp_path / "repo"))


def test_install_no_skill_md_errors(tmp_path: Path) -> None:
    skills.set_skills_dir(tmp_path / "skills")
    empty = tmp_path / "empty"
    empty.mkdir()
    assert skills.skill_install(str(empty)).startswith("[error]")


def test_read_unknown_errors(tmp_path: Path) -> None:
    skills.set_skills_dir(tmp_path / "skills")
    assert skills.skill_read("nope").startswith("[error]")


def test_index_text_empty_points_to_skills_sh(tmp_path: Path) -> None:
    skills.set_skills_dir(tmp_path / "fresh")
    assert "skills.sh" in skills.index_text()


def test_build_tools_includes_skill_tools(tmp_path: Path) -> None:
    names = {t.name for t in build_tools(tmp_path, os_control=False, skills_dir=tmp_path / "sk")}
    assert {"skill_list", "skill_read", "skill_install"} <= names


def test_build_tools_excludes_skill_tools_when_disabled(tmp_path: Path) -> None:
    names = {t.name for t in build_tools(tmp_path, os_control=False, skills_dir=None)}
    assert not any(n.startswith("skill_") for n in names)
