import { AnimatePresence, motion } from "framer-motion";
import type { ConsoleConfig } from "../lib/config";
import { PROVIDER_DEFAULT_MODEL } from "../lib/types";
import type { PolicyMode, Provider } from "../lib/types";
import { Icon } from "./ui/Icon";
import { Field, SelectButtons, TextInput } from "./ui/form";
import { Eyebrow } from "./ui/primitives";

const PROVIDERS: { value: Provider; label: string }[] = [
  { value: "anthropic", label: "Claude" },
  { value: "ollama", label: "Ollama" },
  { value: "openai", label: "OpenAI" },
];

const POLICIES: { value: PolicyMode; label: string }[] = [
  { value: "ask", label: "Ask" },
  { value: "permissive", label: "Permissive" },
  { value: "strict", label: "Strict" },
];

const POLICY_HINT: Record<PolicyMode, string> = {
  ask: "Auto-allow safe reads and in-workspace writes; confirm risky actions.",
  permissive: "Allow everything — no confirmations. Use with care.",
  strict: "Confirm every shell command and every write outside the workspace.",
};

interface SettingsPanelProps {
  open: boolean;
  onToggle: () => void;
  config: ConsoleConfig;
  onChange: (patch: Partial<ConsoleConfig>) => void;
  disabled: boolean;
}

/** Collapsible run-configuration panel: model provider, policy, workspace,
 *  step budget, and the daemon address. Disabled while a task is running so the
 *  config can't drift mid-run. */
export function SettingsPanel({ open, onToggle, config, onChange, disabled }: SettingsPanelProps) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/20">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-2 px-5 py-3.5 text-left"
      >
        <span className="flex items-center gap-2.5">
          <Icon name="spark" className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium">Run settings</span>
          <span className="text-xs font-mono text-muted-foreground">
            {PROVIDERS.find((p) => p.value === config.provider)?.label} · {config.policyMode}
          </span>
        </span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <Icon name="chevron" className="w-4 h-4 text-muted-foreground" />
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className={disabled ? "pointer-events-none opacity-60" : ""}>
              <div className="grid gap-6 border-t border-border/40 px-5 py-5 sm:grid-cols-2">
                <Field label="Model provider">
                  <SelectButtons
                    options={PROVIDERS}
                    value={config.provider}
                    onChange={(provider) => onChange({ provider })}
                    columns={3}
                  />
                </Field>

                <Field label="Policy" hint={POLICY_HINT[config.policyMode]}>
                  <SelectButtons
                    options={POLICIES}
                    value={config.policyMode}
                    onChange={(policyMode) => onChange({ policyMode })}
                    columns={3}
                  />
                </Field>

                <Field label="Model id" hint="Leave blank for the provider default.">
                  <TextInput
                    compact
                    value={config.model}
                    onChange={(e) => onChange({ model: e.currentTarget.value })}
                    placeholder={PROVIDER_DEFAULT_MODEL[config.provider]}
                    spellCheck={false}
                  />
                </Field>

                <Field label="Max steps" hint="Loop iteration budget (default 30).">
                  <TextInput
                    compact
                    inputMode="numeric"
                    value={config.maxSteps}
                    onChange={(e) => onChange({ maxSteps: e.currentTarget.value.replace(/[^0-9]/g, "") })}
                    placeholder="30"
                  />
                </Field>

                <Field label="Workspace" hint="Directory the agent reads/writes in. Blank = daemon default.">
                  <TextInput
                    compact
                    value={config.workspace}
                    onChange={(e) => onChange({ workspace: e.currentTarget.value })}
                    placeholder="~/echlon/workspace"
                    spellCheck={false}
                  />
                </Field>

                <Field label="Daemon address" hint="Where `echlon serve` is listening.">
                  <TextInput
                    compact
                    value={config.base}
                    onChange={(e) => onChange({ base: e.currentTarget.value })}
                    placeholder="http://127.0.0.1:8765"
                    spellCheck={false}
                  />
                </Field>
              </div>

              <div className="border-t border-border/40 px-5 py-3">
                <Eyebrow uppercase>
                  one task runs at a time · risky actions pause for approval
                </Eyebrow>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
