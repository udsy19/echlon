# echlon — desktop console (`app/`)

The Tauri desktop UI for Echlon (PLAN.md Phase 5). A thin watch-and-approve
shell over the headless Python daemon: compose a task, watch the agent's event
stream live, and approve risky actions inline.

## Stack

- **Tauri 2** (Rust shell) + **React 19** + **Vite 7** + **TypeScript**
- **Tailwind CSS v4** with the `[know]` design tokens (infrastructure-grade
  minimal: achromatic, `font-light` headlines, monospace bracket branding)
- **Framer Motion** for all component motion

## Architecture

```
React webview ──invoke()──▶ Rust commands (src-tauri/src/lib.rs) ──HTTP/SSE──▶ echlon daemon :8765
            ◀──Channel<Event>── (parsed SSE)
```

The webview never calls the daemon directly. Every request is routed through
four Rust commands so WKWebView's cross-origin / CSP rules can't block a local
request, and the SSE stream is parsed in one place:

| Command          | Daemon call                   |
| ---------------- | ----------------------------- |
| `daemon_health`  | `GET /health`                 |
| `start_task`     | `POST /run`                   |
| `approve`        | `POST /approve`               |
| `stream_events`  | `GET /events` (SSE → Channel) |

Frontend layout: `lib/` (daemon IPC client, types, config), `hooks/`
(`useAgentSession`, `useDaemonHealth`, `useTheme`), `components/` (composer,
event timeline, approval prompt) and `components/ui/` (design-system primitives).

## Develop

```bash
pnpm install
pnpm tauri dev          # launches the desktop app (needs Rust + Xcode CLT)
```

The app expects the daemon at `http://127.0.0.1:8765` (configurable in Run
settings). Start the real daemon from `../daemon`:

```bash
cd ../daemon && uv run echlon serve
```

### Verify without the real daemon / an API key

A faithful mock of the daemon contract scripts a believable run — including a
risky action that pauses for approval:

```bash
python3 scripts/mock-daemon.py      # http://127.0.0.1:8765
```

Then run `pnpm tauri dev`, type any task, and watch the stream render and the
approval prompt round-trip.

## Build

```bash
pnpm tauri build        # produces a signed-able .app / .dmg under src-tauri/target
```
