"""Echlon CLI — the thin harness to drive and watch the agent loop.

This is the Phase-1 interface; the Tauri desktop app (Phase 5) wraps the same
build_agent() core. See PLAN.md §4.
"""

from __future__ import annotations

import argparse
import sys

from .agent import build_agent
from .config import load_config
from .models import build_model


def _cmd_hello(args: argparse.Namespace) -> int:
    """One Claude round-trip through the provider abstraction (Phase 0 check)."""
    cfg = load_config(provider=args.provider, model_id=args.model)
    model = build_model(cfg)
    msg = [{"role": "user", "content": [{"type": "text", "text": "Reply with exactly: echlon online"}]}]
    resp = model.generate(msg)
    print(f"[model] {cfg.model_id}")
    print(f"[reply] {resp.content}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """Run the full agent loop on a task (Phase 1)."""
    cfg = load_config(
        provider=args.provider,
        model_id=args.model,
        workspace=args.workspace,
        max_steps=args.max_steps,
    )
    print(f"[echlon] model={cfg.model_id} workspace={cfg.workspace} max_steps={cfg.max_steps}\n")
    agent = build_agent(cfg)
    result = agent.run(args.task)
    print("\n[echlon] === final answer ===")
    print(result)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="echlon", description="Local autonomous agent for macOS")
    parser.add_argument("--provider", default=None, help="anthropic | ollama | openai")
    parser.add_argument("--model", default=None, help="LiteLLM model id (overrides provider default)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_hello = sub.add_parser("hello", help="Round-trip one model call")
    p_hello.set_defaults(func=_cmd_hello)

    p_run = sub.add_parser("run", help="Run the agent loop on a task")
    p_run.add_argument("task", help="The task for the agent to perform")
    p_run.add_argument("--workspace", default=None, help="Working directory for the agent")
    p_run.add_argument("--max-steps", type=int, default=None, dest="max_steps")
    p_run.set_defaults(func=_cmd_run)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n[echlon] interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
