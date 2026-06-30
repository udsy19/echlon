"""Connector registry + wiring (no live MCP connections)."""

from __future__ import annotations

import json
from pathlib import Path

from echlon.tools import build_tools, connectors


def test_add_list_remove_roundtrip(tmp_path: Path) -> None:
    connectors.set_connectors_file(tmp_path / "connectors.json")

    out = connectors.connector_add("gcal", json.dumps({"command": "npx", "args": ["-y", "gcal-mcp"]}))
    assert "[ok]" in out
    assert "gcal" in connectors.connector_list()

    saved = json.loads((tmp_path / "connectors.json").read_text())
    assert saved["gcal"]["command"] == "npx"
    assert saved["gcal"]["enabled"] is True  # defaulted on

    assert "[ok]" in connectors.connector_remove("gcal")
    assert "gcal" not in connectors.connector_list()


def test_add_rejects_bad_json(tmp_path: Path) -> None:
    connectors.set_connectors_file(tmp_path / "connectors.json")
    assert connectors.connector_add("x", "{not json").startswith("[error]")


def test_add_rejects_spec_without_command_or_url(tmp_path: Path) -> None:
    connectors.set_connectors_file(tmp_path / "connectors.json")
    assert connectors.connector_add("x", json.dumps({"foo": "bar"})).startswith("[error]")


def test_http_spec_accepted(tmp_path: Path) -> None:
    connectors.set_connectors_file(tmp_path / "connectors.json")
    out = connectors.connector_add("api", json.dumps({"url": "https://example.com/mcp"}))
    assert "[ok]" in out
    assert "example.com" in connectors.connector_list()


def test_remove_unknown_errors(tmp_path: Path) -> None:
    connectors.set_connectors_file(tmp_path / "connectors.json")
    assert connectors.connector_remove("nope").startswith("[error]")


def test_test_unknown_errors(tmp_path: Path) -> None:
    connectors.set_connectors_file(tmp_path / "connectors.json")
    assert connectors.connector_test("nope").startswith("[error]")


def test_load_mcp_tools_empty(tmp_path: Path) -> None:
    connectors.set_connectors_file(tmp_path / "connectors.json")
    assert connectors.load_mcp_tools() == []


def test_disabled_connector_not_loaded(tmp_path: Path) -> None:
    connectors.set_connectors_file(tmp_path / "connectors.json")
    (tmp_path / "connectors.json").write_text(
        json.dumps({"x": {"command": "false", "enabled": False}})
    )
    assert connectors.load_mcp_tools() == []  # disabled → never connected


def test_build_tools_includes_connector_tools(tmp_path: Path) -> None:
    names = {t.name for t in build_tools(tmp_path, os_control=False, connectors_file=tmp_path / "c.json")}
    assert {"connector_list", "connector_add", "connector_remove", "connector_test"} <= names


def test_build_tools_excludes_connector_tools_when_none(tmp_path: Path) -> None:
    names = {t.name for t in build_tools(tmp_path, os_control=False, connectors_file=None)}
    assert not any(n.startswith("connector_") for n in names)
