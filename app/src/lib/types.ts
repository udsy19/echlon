/** Event contract emitted by the echlon daemon over SSE (see daemon/session.py).
 *  Each event is `{ type, data }`. `__closed` is a synthetic marker the Rust
 *  bridge appends when the stream ends. */

export type DaemonEvent =
  | { type: "started"; data: { task: string; model: string } }
  | { type: "plan"; data: { plan: string } }
  | { type: "tool_call"; data: { name: string; arguments: string } }
  | { type: "step"; data: { step: number; observations: string; error: string | null } }
  | { type: "approval_request"; data: { id: string; summary: string } }
  | { type: "approval_timeout"; data: { id: string; summary: string } }
  | { type: "final_answer"; data: { output: string } }
  | { type: "error"; data: { message: string; kind?: string } }
  | { type: "done"; data: { status?: string } }
  | { type: "__closed"; data?: Record<string, never> };

export type DaemonEventType = DaemonEvent["type"];

/** A daemon event tagged with a stable client id + timestamp for rendering. */
export type TimelineEvent = DaemonEvent & { _id: number; _at: number };

export type SessionStatus =
  | "idle"
  | "starting"
  | "running"
  | "awaiting_approval"
  | "done"
  | "error";

export type ApprovalDecision = "once" | "always" | "deny";

export type PolicyMode = "permissive" | "ask" | "strict";

export type Provider = "anthropic" | "ollama" | "openai";

/** Default LiteLLM model id per provider (mirrors daemon config._PROVIDER_DEFAULTS),
 *  shown as the model field's placeholder so the user sees what they'll get. */
export const PROVIDER_DEFAULT_MODEL: Record<Provider, string> = {
  anthropic: "anthropic/claude-opus-4-8",
  ollama: "ollama_chat/qwen2.5-coder:7b",
  openai: "openai/gpt-4o",
};

export interface PendingApproval {
  id: string;
  summary: string;
}

/** Payload posted to `POST /run`. Only `task` is required. */
export interface RunConfig {
  task: string;
  provider?: Provider;
  model?: string;
  policy_mode?: PolicyMode;
  workspace?: string;
  max_steps?: number;
}
