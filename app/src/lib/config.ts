import { DEFAULT_BASE } from "./daemon";
import type { PolicyMode, Provider, RunConfig } from "./types";

/** UI-side run settings. Strings (not numbers) for fields bound to inputs;
 *  empty values mean "let the daemon use its own default". */
export interface ConsoleConfig {
  base: string;
  provider: Provider;
  model: string;
  policyMode: PolicyMode;
  workspace: string;
  maxSteps: string;
}

export const DEFAULT_CONFIG: ConsoleConfig = {
  base: DEFAULT_BASE,
  provider: "anthropic",
  model: "",
  policyMode: "ask",
  workspace: "",
  maxSteps: "",
};

/** Translate console settings + a task into the daemon's `POST /run` payload,
 *  omitting empty optional fields so the daemon falls back to its defaults. */
export function toRunConfig(cfg: ConsoleConfig, task: string): RunConfig {
  const payload: RunConfig = { task: task.trim(), provider: cfg.provider, policy_mode: cfg.policyMode };
  const model = cfg.model.trim();
  if (model) payload.model = model;
  const workspace = cfg.workspace.trim();
  if (workspace) payload.workspace = workspace;
  const steps = Number.parseInt(cfg.maxSteps, 10);
  if (Number.isFinite(steps) && steps > 0) payload.max_steps = steps;
  return payload;
}
