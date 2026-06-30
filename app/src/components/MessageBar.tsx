import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { ConsoleConfig } from "../lib/config";
import { SettingsPanel } from "./SettingsPanel";
import { Icon } from "./ui/Icon";
import { Textarea } from "./ui/form";

interface MessageBarProps {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop: () => void;
  onNew: () => void;
  running: boolean;
  hasConversation: boolean;
  offline: boolean;
  config: ConsoleConfig;
  onConfigChange: (patch: Partial<ConsoleConfig>) => void;
  /** Run settings can't change mid-conversation (the session is already configured). */
  configLocked: boolean;
}

/** The always-present message bar: starts a task when idle, steers when the agent
 *  is mid-turn. Stop ends the current turn; New starts a fresh conversation. */
export function MessageBar({
  value,
  onChange,
  onSend,
  onStop,
  onNew,
  running,
  hasConversation,
  offline,
  config,
  onConfigChange,
  configLocked,
}: MessageBarProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const canSend = value.trim().length > 0 && !offline;

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) onSend();
    }
  }

  return (
    <div className="shrink-0 border-t border-border/40 bg-background/80 backdrop-blur-sm">
      <AnimatePresence initial={false}>
        {settingsOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mx-auto max-w-3xl px-6 pt-4">
              {configLocked && (
                <p className="mb-2 text-xs text-muted-foreground/70">
                  Settings are locked while a conversation is open — start a new one to change them.
                </p>
              )}
              <SettingsPanel
                open
                onToggle={() => setSettingsOpen(false)}
                config={config}
                onChange={onConfigChange}
                disabled={configLocked}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mx-auto max-w-3xl px-6 py-4">
        <div className="relative flex items-end gap-2 rounded-2xl border border-border bg-background p-2 focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20">
          {/* settings toggle */}
          <button
            type="button"
            onClick={() => setSettingsOpen((v) => !v)}
            title="Run settings"
            className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground"
          >
            <Icon name="spark" className="w-[18px] h-[18px]" />
          </button>

          <Textarea
            value={value}
            onChange={(e) => onChange(e.currentTarget.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder={
              offline
                ? "Daemon offline — start it with ./run.sh serve"
                : running
                  ? "Add guidance to steer the agent…"
                  : "Message echlon — describe a task, or ask a question"
            }
            className="min-h-[44px] flex-1 resize-none border-0 bg-transparent px-1 py-2.5 focus:ring-0 focus:border-0"
          />

          {/* stop (while running) */}
          {running && (
            <motion.button
              type="button"
              onClick={onStop}
              whileTap={{ scale: 0.94 }}
              title="Stop the current turn"
              className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-border text-muted-foreground transition-colors hover:text-destructive hover:border-destructive/40"
            >
              <Icon name="stop" className="w-4 h-4" strokeWidth={2} />
            </motion.button>
          )}

          {/* send */}
          <motion.button
            type="button"
            onClick={() => canSend && onSend()}
            disabled={!canSend}
            whileTap={canSend ? { scale: 0.94 } : undefined}
            title={running ? "Send guidance" : "Send"}
            className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-foreground text-background transition-opacity disabled:opacity-30"
          >
            <Icon name="send" className="w-[18px] h-[18px]" strokeWidth={2} />
          </motion.button>
        </div>

        <div className="mt-2 flex items-center justify-between px-1 text-[11px] font-mono text-muted-foreground/60">
          <span>{running ? "agent working — your message will steer it" : "↵ to send · ⇧↵ for a new line"}</span>
          {hasConversation && (
            <button type="button" onClick={onNew} className="flex items-center gap-1.5 transition-colors hover:text-foreground">
              <Icon name="refresh" className="w-3.5 h-3.5" strokeWidth={2} />
              New conversation
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
