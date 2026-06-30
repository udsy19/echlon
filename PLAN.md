# Echlon — Manus, on your Mac

A local-first, autonomous general AI agent for macOS (Apple Silicon). Same shape as
Manus: a single agentic loop driving a "virtual computer" (shell + filesystem +
browser + code execution + network) — but running on *your* machine, with full host
access, and able to run on closed (Claude) **or** open-source (Qwen/etc.) models.

---

## 1. Decisions (locked)

| Decision | Choice | Consequence |
|---|---|---|
| Reasoning model | **Claude API now, provider abstraction from day 1** | Reliable tool-use immediately; open models are a first-class swap, not a bolt-on |
| Open-model support | **Required from Phase 1** | `LLMProvider` interface + retry/repair for flaky tool-calls is foundational |
| Access scope | **Full host access** | Agent acts on real files/apps/browser; sandbox is *opt-in*, not the default |
| Safety | **Configurable guardrail layer** | Default confirms destructive/irreversible ops; can be set fully-permissive |
| Build base | **smolagents + MCP + browser-use** (custom core) | Max control, permissive license, model-agnostic CodeAct; not forking OpenHands |
| Form factor | **Tauri desktop app** (built on a headless daemon) | Daemon (brain) first, Tauri UI wraps it |
| References (borrow, don't fork) | OpenHands, OpenManus, AgenticSeek | Tool wiring, browser integration, local-router/UX patterns |

---

## 2. What Manus actually is (the model we're copying)

- **One agent, one loop** — not a multi-agent orchestra. Per Manus's own engineering
  blog: one tool call per iteration, a **mandatory observe step**, ~50 calls/task.
- The value is **context engineering**, six lessons we bake in from the start:
  1. **Design around the KV-cache** — byte-stable prompt prefix, append-only context,
     explicit cache breakpoints. (Agent traffic is ~100:1 input:output; cached input is ~10× cheaper.)
  2. **Mask, don't remove, tools** — never mutate tool defs mid-task (invalidates cache);
     constrain availability via decode-time masking / response prefill. Prefixed tool
     names (`browser_`, `shell_`, `file_`) make this trivial.
  3. **Filesystem as externalized memory** — offload big observations to files;
     compression must be **restorable** (drop a page body, keep its URL).
  4. **Recitation via `todo.md`** — continuously rewrite a todo file so the current
     objective is re-injected at the end of context every step (fights drift on long tasks).
  5. **Keep errors in context** — never scrub failures; seeing them is how the model adapts.
  6. **Vary formatting** — break few-shot ruts with small structured variation.
- **State** lives in three places: an append-only **event stream**, the recited
  **`todo.md`**, and the **filesystem** workspace.

> Sources: manus.im/blog (Context Engineering for AI Agents); E2B blog; the-decoder
> (Manus uses Claude Sonnet + Qwen); reverse-engineering write-ups (treat multi-agent
> framing as soft — trust the single loop).

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Tauri desktop app (Rust shell + web UI)                       │
│  task input · live event-stream view · embedded browser view  │
│  approval prompts (Allow Once / Always / Deny)                 │
└───────────────▲───────────────────────────────────────────────┘
                │ local IPC / websocket
┌───────────────┴───────────────────────────────────────────────┐
│  Agent daemon (Python, long-running)                           │
│                                                                │
│  ┌── Agent Core (the loop) ──────────────────────────────┐    │
│  │  event stream (append-only) · one action + observe     │    │
│  │  context manager (6 lessons) · todo.md recitation      │    │
│  │  CodeAct action execution (smolagents)                 │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌── LLMProvider (abstraction) ──────────────────────────┐    │
│  │  ClaudeProvider · OpenAICompatProvider (Ollama/MLX/    │    │
│  │  LM Studio/vLLM) · tool-call retry/repair              │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌── Tool layer (MCP servers, prefixed names) ───────────┐    │
│  │  shell_* · file_* · code_* · browser_* · search_* ·    │    │
│  │  message_*                                             │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌── Guardrail / consent engine ─────────────────────────┐    │
│  │  classify action (read / mutate / destructive /        │    │
│  │  network / outside-workspace) → policy → allow/ask/deny│    │
│  └───────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌── Execution backends (selectable per session) ───────┐     │
│  │  HOST (default, full access) · wasm (Pyodide) ·        │     │
│  │  Docker / Apple `container` (opt-in isolation)         │     │
│  └───────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

**Browser:** Playwright over **CDP attach to a headful Chrome** (launched with
`--remote-debugging-port`). Reuses your real logins/cookies, you watch it work live.
Feed the **a11y/DOM-index snapshot** (browser-use style) to the model — works without a
vision model, which matters for local LLMs. Screenshot+vision only as fallback.

**Why Python core + Tauri UI:** the entire agent ecosystem (smolagents, browser-use,
MLX, LiteLLM) is Python. Tauri (small, ~5MB, low-RAM) is a thin watch/approve shell that
talks to the daemon over local IPC. Standard "headless brain + thin UI" split.

---

## 4. Phased roadmap

Each phase is a thin vertical slice that runs end-to-end before the next starts.

### Phase 0 — Scaffold & spec  *(foundation)*
- Repo layout: `daemon/` (Python), `app/` (Tauri), `PLAN.md`, `SPEC.md`.
- Python env (uv), pin deps (smolagents, anthropic, litellm, playwright).
- `LLMProvider` interface skeleton + `ClaudeProvider` stub.
- **Acceptance:** `echlon hello` round-trips one Claude call through the provider.

### Phase 1 — Headless agent loop MVP  *(the brain)*
- Single append-only event-stream loop; one action + mandatory observe.
- Tools: `shell_*`, `file_*`, `code_*` running on **host**.
- `todo.md` recitation + event-stream state.
- Thin CLI harness to drive/observe the loop.
- **Acceptance:** given "scaffold a small project, run it, fix the error," the agent
  completes it autonomously over multiple steps on the real filesystem.

### Phase 2 — Browser + full context engineering
- `browser_*` tool: Playwright CDP attach to headful Chrome, a11y-tree snapshots.
- Implement all six lessons: cache-stable prefix, tool-masking, restorable fs-compression,
  recitation, error retention, format variation.
- **Acceptance:** agent does a real web task (search → open → extract → write a file)
  using your logged-in browser; long tasks (30+ steps) don't drift.

### Phase 3 — Open-source models
- `OpenAICompatProvider` (Ollama / LM Studio / MLX / vLLM).
- Tool-call **retry/repair** for malformed schemas from smaller models.
- **Acceptance:** the same Phase-1 task completes driven by a local Qwen3-class model
  (degraded but functional), selectable via config.

### Phase 4 — Guardrail / consent engine
- Action classifier + policy engine; Allow-Once / Always-Allow / Deny.
- Default policy: auto-allow reads + workspace writes; confirm destructive/irreversible/
  outside-workspace/network-write. Fully-permissive mode available.
- **Acceptance:** `rm -rf` outside workspace triggers a prompt; reads don't.

### Phase 5 — Tauri desktop app  *(product form factor)*
- Daemon exposes IPC/websocket API; Tauri frontend: task input, live event stream,
  embedded browser view, approval prompts, session pause/resume.
- **Acceptance:** drive a full task start-to-finish from the desktop app, watching and
  approving actions live.

### Phase 6 — Hardening & packaging
- Selectable execution backends (wasm / Docker / Apple `container`).
- macOS code signing + notarization; TCC onboarding (Accessibility / Screen Recording
  only if/when desktop GUI control is added — browser-first avoids most of this).
- **Acceptance:** signed `.app` installs and runs on a clean Mac.

---

## 5. Risks & how we handle them

| Risk | Mitigation |
|---|---|
| Full host access → destructive mistakes | Configurable guardrail layer (Phase 4), default-confirm on irreversible ops |
| Open models flake on tool-calls | Retry/repair layer; prefer DOM-index browsing over vision; document min model size (14B+/30B MoE) |
| KV-cache cost/latency | Stable prefix + append-only from Phase 2; never mutate tool defs mid-task |
| Long-task drift | `todo.md` recitation + restorable fs-offload from Phase 2 |
| macOS sandbox parity (no Firecracker) | Host-first by design; Apple `container`/Docker/wasm as opt-in (Phase 6) |
| Scope creep into desktop GUI control | Browser-first; treat native-app GUI control (Agent-S/UI-TARS) as a later optional module |

---

## 6. Out of scope (for now)
- Native desktop GUI control of arbitrary Mac apps (browser covers most needs; revisit later).
- Cloud sync / multi-device / hosted sandboxes (E2B/Daytona) — this is local-first.
- Multi-agent "society" orchestration — start with the single loop Manus actually uses.
