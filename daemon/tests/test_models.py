"""Provider factory + Ollama preflight (offline; preflight HTTP is mocked)."""

from __future__ import annotations

import io
import json

import pytest

from echlon import models
from echlon.config import EchlonConfig


def test_build_model_anthropic_default() -> None:
    m = models.build_model(EchlonConfig(provider="anthropic"))
    assert m.model_id == "anthropic/claude-opus-4-8"


def test_config_rejects_bad_provider() -> None:
    with pytest.raises(ValueError, match="provider"):
        EchlonConfig(provider="bogus")


def test_config_rejects_bad_policy_mode() -> None:
    with pytest.raises(ValueError, match="policy_mode"):
        EchlonConfig(policy_mode="bogus")


def test_anthropic_ready_ok(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    models.ensure_anthropic_ready(EchlonConfig(provider="anthropic"))  # no raise


def test_anthropic_ready_missing(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        models.ensure_anthropic_ready(EchlonConfig(provider="anthropic"))


def test_build_model_ollama_sets_api_base_and_key() -> None:
    cfg = EchlonConfig(provider="ollama", model_id="ollama_chat/qwen2.5-coder:3b")
    m = models.build_model(cfg)
    assert m.model_id == "ollama_chat/qwen2.5-coder:3b"
    assert m.api_base == "http://localhost:11434"
    assert m.api_key == "not-needed"


def _fake_tags(monkeypatch, payload: dict) -> None:
    def fake_urlopen(url, timeout=0):  # noqa: ARG001
        return io.BytesIO(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(models.urllib.request, "urlopen", fake_urlopen)


def test_ollama_ready_ok(monkeypatch) -> None:
    _fake_tags(monkeypatch, {"models": [{"name": "qwen2.5-coder:3b"}]})
    cfg = EchlonConfig(provider="ollama", model_id="ollama_chat/qwen2.5-coder:3b")
    ensure = models.ensure_ollama_ready
    ensure(cfg)  # should not raise


def test_ollama_ready_model_missing(monkeypatch) -> None:
    _fake_tags(monkeypatch, {"models": [{"name": "llama3.2:3b"}]})
    cfg = EchlonConfig(provider="ollama", model_id="ollama_chat/qwen2.5-coder:3b")
    with pytest.raises(RuntimeError, match="ollama pull qwen2.5-coder:3b"):
        models.ensure_ollama_ready(cfg)


def test_ollama_ready_unreachable(monkeypatch) -> None:
    def boom(url, timeout=0):  # noqa: ARG001
        raise OSError("connection refused")

    monkeypatch.setattr(models.urllib.request, "urlopen", boom)
    cfg = EchlonConfig(provider="ollama")
    with pytest.raises(RuntimeError, match="ollama serve"):
        models.ensure_ollama_ready(cfg)
