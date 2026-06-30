"""Model provider factory.

One code path (`LiteLLMModel`) serves both Claude and any OpenAI-compatible or
Ollama endpoint — this is the "works on closed *and* open-source models from
day one" requirement (PLAN.md §1). We do not hand-roll a parallel provider
interface; LiteLLM already is one.
"""

from __future__ import annotations

from smolagents import LiteLLMModel

from .config import EchlonConfig


def build_model(cfg: EchlonConfig) -> LiteLLMModel:
    """Construct a smolagents model from config.

    Notes:
      - For provider=anthropic we leave api_key=None so LiteLLM reads
        ANTHROPIC_API_KEY from the environment.
      - Opus 4.8 / Sonnet 4.6 use adaptive thinking; we send no temperature
        or budget_tokens (LiteLLMModel doesn't inject them), so the default
        request is valid for the whole current Claude lineup.
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
