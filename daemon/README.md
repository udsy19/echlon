# echlon (daemon)

The Python agent core for Echlon — a local-first autonomous agent for macOS.
See `../PLAN.md` for the full architecture and roadmap.

This is Phase 1: a single CodeAct loop (smolagents) driving a real shell,
filesystem, and Python execution on the host, with Manus-style operating
behavior (todo recitation, keep-errors-visible, filesystem-as-memory).

## Setup

```bash
cd daemon
uv sync
cp .env.example .env   # then add your ANTHROPIC_API_KEY
```

The model layer goes through LiteLLM, so the same code runs on Claude or any
OpenAI-compatible / Ollama endpoint — switch with env vars (see `.env.example`).

## Use

```bash
# Phase 0 check — one model round-trip through the provider abstraction:
uv run echlon hello

# Phase 1 — run the agent loop on a task (operates in ./workspace):
uv run echlon run "Create a Python script that prints the first 20 primes, run it, and fix any errors."

# Use a cheaper agentic model, or a local open-source one:
uv run echlon --model anthropic/claude-sonnet-4-6 run "..."
uv run echlon --provider ollama run "..."     # needs Ollama running
```

## Daemon API (for the desktop UI)

`echlon serve` exposes the agent over local HTTP + SSE — the interface the Tauri
app (Phase 5) consumes. One active task at a time.

```bash
uv run echlon serve                                   # http://127.0.0.1:8765
curl -XPOST localhost:8765/run -d '{"task":"..."}'    # -> {"session_id"}
curl -N "localhost:8765/events?session=<id>"          # SSE: started/plan/tool_call/
                                                       #      step/approval_request/
                                                       #      final_answer/done
curl -XPOST localhost:8765/approve \
  -d '{"session":"<id>","id":"<approval_id>","decision":"once"}'  # once|always|deny
```

Risky actions surface as `approval_request` events; the UI answers via `/approve`.

## Guardrails

Full host access is gated by a configurable policy (default `ask`): reads and
in-workspace writes run freely; destructive shell commands and writes outside
the workspace are confirmed (interactively) or blocked (non-interactive).

```bash
uv run echlon run "..."              # ask (default)
uv run echlon run --allow-all "..."  # permissive — no confirmations
uv run echlon run --strict "..."     # confirm every shell command
```

## Test

```bash
uv run pytest          # offline loop test — no API key required
```

## Layout

```
src/echlon/
  config.py     # env-driven config + provider defaults
  models.py     # LiteLLM model factory (Claude / Ollama / OpenAI-compatible)
  agent.py      # CodeAgent assembly + Manus operating instructions
  cli.py        # `echlon hello` / `echlon run`
  tools/        # shell_exec, file_read/write/edit, todo_read/write (host access)
tests/
  test_loop.py  # fake-model loop verification
```
