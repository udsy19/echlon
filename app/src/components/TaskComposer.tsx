import { useState } from "react";
import type { HealthState } from "../hooks/useDaemonHealth";
import type { ConsoleConfig } from "../lib/config";
import type { SessionStatus } from "../lib/types";
import { SettingsPanel } from "./SettingsPanel";
import { Button } from "./ui/Button";
import { Icon } from "./ui/Icon";
import { Textarea } from "./ui/form";
import { Eyebrow, LiveDot, Spinner } from "./ui/primitives";

interface TaskComposerProps {
  config: ConsoleConfig;
  onConfigChange: (patch: Partial<ConsoleConfig>) => void;
  onRun: (task: string) => void;
  onReset: () => void;
  status: SessionStatus;
  isBusy: boolean;
  health: HealthState;
}

/** Task input + run controls + collapsible settings. */
export function TaskComposer({
  config,
  onConfigChange,
  onRun,
  onReset,
  status,
  isBusy,
  health,
}: TaskComposerProps) {
  const [task, setTask] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);

  const offline = health === "offline";
  const canRun = task.trim().length > 0 && !isBusy && !offline;

  function submit() {
    if (!canRun) return;
    onRun(task);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  }

  const finished = status === "done" || status === "error";

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <LiveDot tone={isBusy ? "emerald" : "muted"} pulse={isBusy} />
        <Eyebrow>{isBusy ? "task in progress" : "new task"}</Eyebrow>
      </div>

      <Textarea
        value={task}
        onChange={(e) => setTask(e.currentTarget.value)}
        onKeyDown={onKeyDown}
        rows={3}
        disabled={isBusy}
        placeholder="Describe a task — e.g. “Scaffold a small Python project, run it, and fix any errors.”"
        className="selectable text-base leading-relaxed"
      />

      <SettingsPanel
        open={settingsOpen}
        onToggle={() => setSettingsOpen((v) => !v)}
        config={config}
        onChange={onConfigChange}
        disabled={isBusy}
      />

      <div className="flex flex-wrap items-center gap-4">
        <Button onClick={submit} disabled={!canRun}>
          {status === "starting" ? (
            <>
              <Spinner /> Starting…
            </>
          ) : isBusy ? (
            <>
              <Spinner /> Running…
            </>
          ) : (
            <>
              Run task
              <Icon name="send" className="w-[18px] h-[18px]" strokeWidth={2} />
            </>
          )}
        </Button>

        {finished && (
          <Button
            variant="ghost"
            onClick={() => {
              onReset();
              setTask("");
            }}
          >
            <Icon name="refresh" className="w-4 h-4" strokeWidth={2} />
            New task
          </Button>
        )}

        <span className="ml-auto text-xs font-mono text-muted-foreground/70">
          {offline ? "daemon offline" : "⌘↵ to run"}
        </span>
      </div>
    </section>
  );
}
