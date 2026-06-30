/** IPC client for the echlon daemon. Every call is routed through the Tauri
 *  Rust backend (see src-tauri/src/lib.rs) so the webview never makes a
 *  cross-origin request itself. */

import { Channel, invoke } from "@tauri-apps/api/core";
import type { ApprovalDecision, Connector, DaemonEvent, RunConfig, Skill } from "./types";

export const DEFAULT_BASE = "http://127.0.0.1:8765";

/** True when running inside the Tauri shell (vs. a plain browser dev server). */
export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

const NOT_TAURI =
  "The echlon backend is only reachable from the desktop app. Launch it with `pnpm tauri dev`.";

/** `GET /health` — true only if the daemon answers `{status:"ok"}`. */
export async function checkHealth(base: string): Promise<boolean> {
  if (!isTauri()) return false;
  try {
    return await invoke<boolean>("daemon_health", { base });
  } catch {
    return false;
  }
}

/** `POST /run` — start a task, resolve with the new session id. */
export async function startTask(base: string, payload: RunConfig): Promise<string> {
  if (!isTauri()) throw new Error(NOT_TAURI);
  return invoke<string>("start_task", { base, payload });
}

/** `POST /message` — send a message to an open session. The daemon decides
 *  whether it starts a new turn or steers the running one; returns {ok, mode}. */
export async function sendMessage(
  base: string,
  session: string,
  text: string,
): Promise<{ ok: boolean; mode?: string; reason?: string }> {
  if (!isTauri()) throw new Error(NOT_TAURI);
  return invoke("send_message", { base, session, text });
}

/** `POST /cancel` — cancel the in-progress turn (session stays open). */
export async function cancelTurn(base: string, session: string): Promise<boolean> {
  if (!isTauri()) throw new Error(NOT_TAURI);
  return invoke<boolean>("cancel_turn", { base, session });
}

/** `POST /close` — end the conversation/session. */
export async function closeSession(base: string, session: string): Promise<boolean> {
  if (!isTauri()) throw new Error(NOT_TAURI);
  return invoke<boolean>("close_session", { base, session });
}

/** `POST /approve` — answer a pending approval. */
export async function approve(
  base: string,
  session: string,
  id: string,
  decision: ApprovalDecision,
): Promise<boolean> {
  if (!isTauri()) throw new Error(NOT_TAURI);
  return invoke<boolean>("approve", { base, session, id, decision });
}

/** `GET /skills` — installed skills. */
export async function listSkills(base: string): Promise<Skill[]> {
  if (!isTauri()) return [];
  const r = await invoke<{ skills: Skill[] }>("list_skills", { base });
  return r.skills ?? [];
}

/** `POST /skills/install` — install a skill from owner/repo (returns a status line). */
export async function installSkill(base: string, source: string): Promise<string> {
  if (!isTauri()) throw new Error(NOT_TAURI);
  const r = await invoke<{ result: string }>("install_skill", { base, source });
  return r.result;
}

/** `GET /connectors` — configured MCP connectors. */
export async function listConnectors(base: string): Promise<Connector[]> {
  if (!isTauri()) return [];
  const r = await invoke<{ connectors: Connector[] }>("list_connectors", { base });
  return r.connectors ?? [];
}

/** `POST /connectors/add` — add/update a connector (spec is the MCP server object). */
export async function addConnector(base: string, name: string, spec: unknown): Promise<string> {
  if (!isTauri()) throw new Error(NOT_TAURI);
  const r = await invoke<{ result: string }>("add_connector", { base, name, spec });
  return r.result;
}

/** `POST /connectors/remove` — remove a connector. */
export async function removeConnector(base: string, name: string): Promise<string> {
  if (!isTauri()) throw new Error(NOT_TAURI);
  const r = await invoke<{ result: string }>("remove_connector", { base, name });
  return r.result;
}

/** Open the SSE stream for a session. `onEvent` fires for every event until the
 *  stream closes; the returned promise resolves when it does (or rejects on a
 *  transport error). */
export function streamEvents(
  base: string,
  session: string,
  onEvent: (event: DaemonEvent) => void,
): Promise<void> {
  if (!isTauri()) return Promise.reject(new Error(NOT_TAURI));
  const channel = new Channel<DaemonEvent>();
  channel.onmessage = onEvent;
  return invoke<void>("stream_events", { base, session, onEvent: channel });
}
