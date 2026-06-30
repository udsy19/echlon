#!/usr/bin/env bash
#
# Echlon launcher — one entry point for running and testing the app.
#
#   ./run.sh setup            install deps (daemon + UI) and browser
#   ./run.sh doctor           check the environment is ready (keys, perms, deps)
#   ./run.sh hello            one model round-trip (cheapest end-to-end check)
#   ./run.sh task "<task>"    run the agent on a task in the terminal (pass flags too)
#   ./run.sh serve            start the daemon (HTTP/SSE on :8765) for the UI
#   ./run.sh ui               start the desktop UI dev server (needs `serve` running)
#   ./run.sh test             run the test suites (daemon pytest + UI typecheck)
#   ./run.sh help             show this help
#
# Examples:
#   ./run.sh task "summarize the README" --allow-all
#   ./run.sh task "open Calculator and type 2+2" --provider anthropic
#   ./run.sh hello --provider ollama
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON="$ROOT/daemon"

# The UI lives in a separate git worktree; locate it without hardcoding the path.
ui_app_dir() {
  local wt
  wt="$(git -C "$ROOT" worktree list 2>/dev/null | awk '/\[ui/{print $1; exit}')"
  [ -n "$wt" ] && [ -d "$wt/app" ] && echo "$wt/app"
}

npm_runner() { command -v pnpm >/dev/null 2>&1 && echo pnpm || echo npm; }

need_uv() {
  command -v uv >/dev/null 2>&1 || { echo "✖ 'uv' not found — install from https://docs.astral.sh/uv/"; exit 1; }
}

dae() { need_uv; ( cd "$DAEMON" && uv run "$@" ); }

cmd_setup() {
  need_uv
  echo "▶ daemon deps (uv sync)…"
  ( cd "$DAEMON" && uv sync )
  echo "▶ Playwright Chromium (for browser tasks)…"
  ( cd "$DAEMON" && uv run playwright install chromium ) || echo "  (skip) playwright install failed"
  local ui; ui="$(ui_app_dir)"
  if [ -n "$ui" ]; then
    echo "▶ UI deps ($(npm_runner) install)…"
    ( cd "$ui" && "$(npm_runner)" install )
  else
    echo "  (skip) UI worktree not found"
  fi
  echo "✔ setup done — next: ./run.sh doctor"
}

cmd_doctor() {
  need_uv
  echo "── Echlon doctor ──"
  echo -n "uv:             "; uv --version
  echo -n "ANTHROPIC key:  "; [ -f "$DAEMON/.env" ] && grep -q '^ANTHROPIC_API_KEY=.\+' "$DAEMON/.env" && echo "set (daemon/.env)" || echo "NOT set — add to daemon/.env, or use --provider ollama"
  echo -n "Ollama:         "; curl -s -m 2 http://localhost:11434/api/tags >/dev/null 2>&1 && echo "up (local models available)" || echo "down (run 'ollama serve' for local models)"
  echo -n "screencapture:  "; command -v screencapture >/dev/null && echo "present" || echo "MISSING"
  echo "OS control perms:"
  dae python - <<'PY' || true
from echlon.tools.computer import ensure_os_control_ready
try:
    ensure_os_control_ready()
    print("  ✔ Screen Recording + Accessibility granted — full desktop control ready")
except Exception as e:
    print("  ✖", e)
PY
  local ui; ui="$(ui_app_dir)"
  echo -n "UI worktree:    "; [ -n "$ui" ] && echo "$ui" || echo "not found"
}

cmd_hello() { dae echlon hello "$@"; }

cmd_task() {
  [ "$#" -ge 1 ] || { echo "usage: ./run.sh task \"<task>\" [flags]"; exit 1; }
  dae echlon run "$@"
}

cmd_serve() { dae echlon serve "$@"; }

cmd_ui() {
  local ui; ui="$(ui_app_dir)"
  [ -n "$ui" ] || { echo "✖ UI worktree not found (expected a worktree on a 'ui' branch)"; exit 1; }
  if ! command -v cargo >/dev/null 2>&1; then
    echo "✖ The desktop app (Tauri) needs Rust, which isn't installed."
    echo "  Install it once, then re-run './run.sh ui':"
    echo "    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"
    echo "    source \"\$HOME/.cargo/env\""
    exit 1
  fi
  echo "▶ Desktop app (tauri dev). The daemon must be running too: ./run.sh serve (other terminal)"
  # tauri dev runs Vite (beforeDevCommand) + compiles the Rust shell. The webview
  # reaches the daemon only through this Rust shell, so a plain browser won't work.
  ( cd "$ui" && "$(npm_runner)" tauri dev )
}

cmd_test() {
  echo "▶ daemon tests (pytest)…"
  dae pytest -q
  local ui; ui="$(ui_app_dir)"
  if [ -n "$ui" ]; then
    echo "▶ UI typecheck (tsc)…"
    ( cd "$ui" && npx tsc --noEmit ) && echo "✔ UI typecheck clean"
  fi
}

cmd_help() { sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

case "${1:-help}" in
  setup)  shift; cmd_setup "$@";;
  doctor) shift; cmd_doctor "$@";;
  hello)  shift; cmd_hello "$@";;
  task)   shift; cmd_task "$@";;
  serve)  shift; cmd_serve "$@";;
  ui)     shift; cmd_ui "$@";;
  test)   shift; cmd_test "$@";;
  help|-h|--help) cmd_help;;
  *) echo "unknown command: $1"; echo; cmd_help; exit 1;;
esac
