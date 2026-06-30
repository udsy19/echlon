"""Model provider factory.

One code path (`LiteLLMModel`) serves both Claude and any OpenAI-compatible or
Ollama endpoint — this is the "works on closed *and* open-source models from
day one" requirement (PLAN.md §1). We do not hand-roll a parallel provider
interface; LiteLLM already is one.

Tool-call/code-block repair for weaker local models is NOT reimplemented here:
smolagents' parser already accepts <code> tags, markdown fences, and raw code,
and feeds a corrective message back on failure (keep-errors-visible). We add
only an Ollama preflight, which LiteLLM does not provide.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from smolagents import LiteLLMModel

from .config import EchlonConfig


def build_model(cfg: EchlonConfig) -> LiteLLMModel:
    """Construct a smolagents model from config (pure — no network).

    Notes:
      - For provider=anthropic we leave api_key=None so LiteLLM reads
        ANTHROPIC_API_KEY from the environment.
      - Opus 4.8 / Sonnet 4.6 use adaptive thinking; we send no temperature
        or budget_tokens (LiteLLMModel doesn't inject them), so the default
        request is valid for the whole current Claude lineup.
      - For ollama_chat ids LiteLLMModel auto-flattens messages to text.
    """
    kwargs: dict[str, object] = {"model_id": cfg.model_id}
    if cfg.api_base:
        kwargs["api_base"] = cfg.api_base
    if cfg.api_key:
        kwargs["api_key"] = cfg.api_key
    elif cfg.provider != "anthropic":
        # Local servers (Ollama / LM Studio) usually ignore the key but LiteLLM
        # requires a non-empty one for openai-compatible routes.
        kwargs["api_key"] = "not-needed"
    return LiteLLMModel(**kwargs)  # type: ignore[arg-type]


def ensure_anthropic_ready(cfg: EchlonConfig) -> None:
    """Fail early if no Anthropic credential is available (LiteLLM's auth error
    is opaque and only surfaces mid-run)."""
    if cfg.api_key or os.getenv("ANTHROPIC_API_KEY"):
        return
    raise RuntimeError(
        "ANTHROPIC_API_KEY is not set. Add it to daemon/.env (or the environment), "
        "or run with a local model: --provider ollama."
    )


def ensure_ready(cfg: EchlonConfig) -> None:
    """Provider-appropriate preflight."""
    if cfg.provider == "anthropic":
        ensure_anthropic_ready(cfg)
    elif cfg.provider == "ollama":
        ensure_ollama_ready(cfg)


def _ollama_model_name(model_id: str) -> str:
    """Strip the LiteLLM provider prefix: 'ollama_chat/qwen2.5-coder:7b' -> 'qwen2.5-coder:7b'."""
    return model_id.split("/", 1)[1] if "/" in model_id else model_id


def ensure_ollama_ready(cfg: EchlonConfig, *, timeout: float = 5.0) -> None:
    """Fail early with an actionable message if the Ollama model can't be served.

    Checks the daemon is reachable and the requested model is pulled. Raises
    RuntimeError with the exact command to fix it; LiteLLM's own errors here are
    opaque.
    """
    base = (cfg.api_base or "http://localhost:11434").rstrip("/")
    want = _ollama_model_name(cfg.model_id)
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=timeout) as resp:
            tags = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(
            f"Ollama is not reachable at {base} ({exc}). Start it with `ollama serve`."
        ) from exc

    available = {m.get("name", "") for m in tags.get("models", [])}
    # Ollama reports names with an explicit tag (':latest' when none given).
    if want not in available and f"{want}:latest" not in available:
        names = ", ".join(sorted(available)) or "(none)"
        raise RuntimeError(
            f"Ollama model '{want}' is not pulled. Run `ollama pull {want}`. "
            f"Available: {names}"
        )
