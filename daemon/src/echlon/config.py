"""Configuration loading for the Echlon agent.

The provider abstraction is deliberately thin: smolagents + LiteLLM already
abstract over Claude and open-source models, so a config object that selects a
model id (+ optional api_base/api_key) is all we need. See PLAN.md §1.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Default model ids per provider, as LiteLLM-prefixed strings.
# Claude is the default driver; open-source models are first-class swaps.
_PROVIDER_DEFAULTS = {
    "anthropic": "anthropic/claude-opus-4-8",
    "ollama": "ollama_chat/qwen2.5-coder:7b",
    "openai": "openai/gpt-4o",
}

_DEFAULT_API_BASE = {
    "ollama": "http://localhost:11434",
}


@dataclass
class EchlonConfig:
    """Runtime configuration for a single agent session."""

    provider: str = "anthropic"
    model_id: str = ""
    api_key: str | None = None
    api_base: str | None = None
    workspace: Path = field(default_factory=lambda: Path.cwd() / "workspace")
    max_steps: int = 30
    planning_interval: int | None = 4
    policy_mode: str = "ask"  # permissive | ask | strict (PLAN.md §4)
    os_control: bool = True  # expose screen/mouse/keyboard tools (whole-desktop control)

    def __post_init__(self) -> None:
        if self.provider not in _PROVIDER_DEFAULTS:
            raise ValueError(
                f"unknown provider {self.provider!r} (use {' | '.join(_PROVIDER_DEFAULTS)})"
            )
        if self.policy_mode not in ("permissive", "ask", "strict"):
            raise ValueError(
                f"unknown policy_mode {self.policy_mode!r} (use permissive | ask | strict)"
            )
        if self.max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        if not self.model_id:
            self.model_id = _PROVIDER_DEFAULTS.get(self.provider, _PROVIDER_DEFAULTS["anthropic"])
        if self.api_base is None:
            self.api_base = _DEFAULT_API_BASE.get(self.provider)
        self.workspace = Path(self.workspace).expanduser().resolve()


def load_config(**overrides: object) -> EchlonConfig:
    """Build an EchlonConfig from environment variables, then apply overrides.

    Environment variables (all optional):
      ECHLON_PROVIDER       provider key: anthropic | ollama | openai
      ECHLON_MODEL_ID       LiteLLM model id (overrides the provider default)
      ECHLON_API_BASE       base URL for local / self-hosted model servers
      ECHLON_WORKSPACE      directory the agent reads/writes in
      ECHLON_MAX_STEPS      max agent loop iterations
      ANTHROPIC_API_KEY     read by LiteLLM directly when provider=anthropic
    """
    load_dotenv()

    env: dict[str, object] = {}
    if v := os.getenv("ECHLON_PROVIDER"):
        env["provider"] = v
    if v := os.getenv("ECHLON_MODEL_ID"):
        env["model_id"] = v
    if v := os.getenv("ECHLON_API_BASE"):
        env["api_base"] = v
    if v := os.getenv("ECHLON_WORKSPACE"):
        env["workspace"] = Path(v)
    if v := os.getenv("ECHLON_MAX_STEPS"):
        env["max_steps"] = int(v)
    if v := os.getenv("ECHLON_POLICY_MODE"):
        env["policy_mode"] = v
    if (v := os.getenv("ECHLON_OS_CONTROL")) is not None:
        env["os_control"] = v.strip().lower() not in ("0", "false", "no", "off")

    env.update({k: v for k, v in overrides.items() if v is not None})
    return EchlonConfig(**env)  # type: ignore[arg-type]
