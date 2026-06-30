import { useCallback, useState } from "react";
import { Header } from "./components/Header";
import { Conversation } from "./components/Conversation";
import { MessageBar } from "./components/MessageBar";
import { ConnectionNotice } from "./components/ConnectionNotice";
import { BackgroundBlobs } from "./components/ui/BackgroundBlobs";
import { useAgentSession } from "./hooks/useAgentSession";
import { useDaemonHealth } from "./hooks/useDaemonHealth";
import { useTheme } from "./hooks/useTheme";
import { DEFAULT_CONFIG, toRunConfig, type ConsoleConfig } from "./lib/config";

export default function App() {
  const { theme, toggle } = useTheme();
  const [config, setConfig] = useState<ConsoleConfig>(DEFAULT_CONFIG);
  const [draft, setDraft] = useState("");
  const { state: health, refresh: refreshHealth } = useDaemonHealth(config.base);
  const session = useAgentSession(config.base);

  const patchConfig = useCallback((patch: Partial<ConsoleConfig>) => {
    setConfig((c) => ({ ...c, ...patch }));
  }, []);

  const onSend = useCallback(() => {
    const text = draft.trim();
    if (!text) return;
    void session.send(text, toRunConfig(config, text));
    setDraft("");
  }, [draft, config, session]);

  return (
    <div className="relative flex h-full flex-col overflow-hidden">
      <BackgroundBlobs />
      <Header health={health} onRefreshHealth={refreshHealth} theme={theme} onToggleTheme={toggle} />

      {health === "offline" && <ConnectionNotice base={config.base} onRetry={refreshHealth} />}

      <main className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1">
          <Conversation
            events={session.events}
            status={session.status}
            pending={session.pending}
            onDecide={session.decide}
            onExample={setDraft}
          />
        </div>

        <MessageBar
          value={draft}
          onChange={setDraft}
          onSend={onSend}
          onStop={session.cancel}
          onNew={session.newConversation}
          running={session.isBusy}
          hasConversation={session.hasConversation}
          offline={health === "offline"}
          config={config}
          onConfigChange={patchConfig}
          configLocked={session.hasConversation}
        />
      </main>
    </div>
  );
}
