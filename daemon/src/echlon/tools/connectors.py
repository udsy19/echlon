"""Connectors — MCP integrations the agent configures for itself.

An MCP connector gives the agent real tools for an external service (calendar,
gmail, drive, github, …). The agent manages a registry (connectors.json) and can
add a connector, test it live, and self-heal when it fails. Enabled connectors
load at the start of a conversation and their tools join the agent's toolset.

Where no API/MCP exists, the agent falls back to the logged-in browser (browser.py
runs a persistent Chrome profile signed in to the user's accounts).

Registry entry (per name):
  stdio:  {"command": "npx", "args": ["-y", "<server>"], "env": {...}, "enabled": true}
  http:   {"url": "https://…/mcp", "transport": "streamable-http", "enabled": true}
"""

from __future__ import annotations

import json
from pathlib import Path

from smolagents import MCPClient, tool

from ..logsetup import get_logger

log = get_logger(__name__)

_connectors_file: Path = Path.home() / "echlon" / "connectors.json"
_clients: list[MCPClient] = []  # open connections for the current session


def set_connectors_file(path: Path) -> Path:
    global _connectors_file
    _connectors_file = Path(path).expanduser().resolve()
    _connectors_file.parent.mkdir(parents=True, exist_ok=True)
    return _connectors_file


def _load() -> dict:
    if not _connectors_file.exists():
        return {}
    try:
        data = json.loads(_connectors_file.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save(cfg: dict) -> None:
    _connectors_file.parent.mkdir(parents=True, exist_ok=True)
    _connectors_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _params(spec: dict):
    """Build MCPClient server params from a registry spec (http dict or stdio)."""
    if "url" in spec:
        return {"url": spec["url"], "transport": spec.get("transport", "streamable-http")}
    from mcp import StdioServerParameters

    return StdioServerParameters(
        command=spec["command"], args=spec.get("args", []), env=spec.get("env") or None
    )


def load_mcp_tools() -> list:
    """Open every enabled connector best-effort and return all their tools.

    A connector that fails to connect is logged and skipped — it never crashes the
    agent (so the agent can later connector_test and fix it).
    """
    tools: list = []
    for name, spec in _load().items():
        if not spec.get("enabled", True):
            continue
        try:
            client = MCPClient(_params(spec), structured_output=False)
            got = client.get_tools()
            _clients.append(client)
            tools.extend(got)
            log.info("connector loaded", extra={"connector": name, "tools": len(got)})
        except Exception as exc:  # noqa: BLE001 — surface, don't crash the agent
            log.error("connector failed to load", extra={"connector": name, "error": str(exc)})
    return tools


def close_all() -> None:
    """Disconnect every open connector (called when a conversation ends)."""
    global _clients
    for client in _clients:
        try:
            client.disconnect()
        except Exception:
            pass
    _clients = []


@tool
def connector_list() -> str:
    """List the MCP connectors (integrations) configured for the agent."""
    cfg = _load()
    if not cfg:
        return ("No connectors configured. To integrate a service (calendar, gmail, github, …), "
                "find its MCP server and add it with connector_add; or use the logged-in browser.")
    lines = []
    for name, spec in cfg.items():
        where = spec["url"] if "url" in spec else f"{spec.get('command','')} {' '.join(spec.get('args', []))}".strip()
        lines.append(f"- {name}: {'enabled' if spec.get('enabled', True) else 'disabled'} — {where}")
    return "Configured connectors (changes take effect on the next conversation):\n" + "\n".join(lines)


@tool
def connector_add(name: str, spec_json: str) -> str:
    """Add or update an MCP connector for an external service.

    Its tools become available on the next conversation; use connector_test to
    verify it works now and fix it if not.

    Args:
        name: short id for the connector, e.g. "gcal".
        spec_json: a JSON object — for a stdio server
            {"command":"npx","args":["-y","<server-pkg>"],"env":{"KEY":"val"}}, or for
            an HTTP server {"url":"https://…/mcp","transport":"streamable-http"}.
    """
    try:
        spec = json.loads(spec_json)
    except json.JSONDecodeError as exc:
        return f"[error] spec_json is not valid JSON: {exc}"
    if not isinstance(spec, dict) or not ("command" in spec or "url" in spec):
        return "[error] spec must be a JSON object with either 'command' (stdio) or 'url' (http)."
    spec.setdefault("enabled", True)
    cfg = _load()
    cfg[name] = spec
    _save(cfg)
    return f"[ok] saved connector {name!r}. Run connector_test('{name}') to verify it; it loads on the next conversation."


@tool
def connector_remove(name: str) -> str:
    """Remove a configured MCP connector.

    Args:
        name: the connector id to remove.
    """
    cfg = _load()
    if name not in cfg:
        return f"[error] no connector named {name!r}."
    del cfg[name]
    _save(cfg)
    return f"[ok] removed connector {name!r}."


@tool
def connector_test(name: str) -> str:
    """Connect to a configured connector right now and report its tools — or the
    error, so you can fix the spec (or install the server) and retry until it works.

    Args:
        name: the connector id to test.
    """
    spec = _load().get(name)
    if spec is None:
        return f"[error] no connector named {name!r}. Add it with connector_add first."
    try:
        client = MCPClient(_params(spec), structured_output=False)
        try:
            names = [t.name for t in client.get_tools()]
        finally:
            client.disconnect()
        return f"[ok] {name} connected. Tools: {', '.join(names) or '(none)'}."
    except Exception as exc:  # noqa: BLE001
        return f"[error] {name} failed to connect: {str(exc)[:400]}. Fix the spec or install the server, then retry."


CONNECTOR_TOOLS = [connector_list, connector_add, connector_remove, connector_test]
