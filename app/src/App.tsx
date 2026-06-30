import { useCallback, useState } from "react";
import { Header } from "./components/Header";
import { TaskComposer } from "./components/TaskComposer";
import { EventStream } from "./components/EventStream";
import { ConnectionNotice } from "./components/ConnectionNotice";
import { BackgroundBlobs } from "./components/ui/BackgroundBlobs";
import { useAgentSession } from "./hooks/useAgentSession";
import { useDaemonHealth } from "./hooks/useDaemonHealth";
import { useTheme } from "./hooks/useTheme";
import { DEFAULT_CONFIG, toRunConfig, type ConsoleConfig } from "./lib/config";

export default function App() {
  const { theme, toggle } = useTheme();
  const [config, setConfig] = useState<ConsoleConfig>(DEFAULT_CONFIG);
  const { state: health, refresh: refreshHealth } = useDaemonHealth(config.base);
  const session = useAgentSession(config.base);

  const patchConfig = useCallback((patch: Partial<ConsoleConfig>) => {
    setConfig((c) => ({ ...c, ...patch }));
  }, []);

  const onRun = useCallback(
    (task: string) => {
      void session.run(toRunConfig(config, task));
    },
    [config, session],
  );

  return (
    <div className="relative flex h-full flex-col overflow-hidden">
      <BackgroundBlobs />
      <Header health={health} onRefreshHealth={refreshHealth} theme={theme} onToggleTheme={toggle} />

      {health === "offline" && <ConnectionNotice base={config.base} onRetry={refreshHealth} />}

      <main className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* Composer / settings pane */}
        <div className="shrink-0 overflow-y-auto scroll-thin border-b border-border/40 px-6 py-6 lg:w-[440px] lg:border-b-0 lg:border-r lg:py-8">
          <TaskComposer
            config={config}
            onConfigChange={patchConfig}
            onRun={onRun}
            onReset={session.reset}
            status={session.status}
            isBusy={session.isBusy}
            health={health}
          />
        </div>

        {/* Live event stream */}
        <div className="min-h-0 flex-1">
          <EventStream
            events={session.events}
            status={session.status}
            pending={session.pending}
            onDecide={session.decide}
          />
        </div>
      </main>
    </div>
  );
}
