import { motion } from "framer-motion";
import type { HealthState } from "../hooks/useDaemonHealth";
import { cn } from "../lib/cn";
import { Icon } from "./ui/Icon";
import { LiveDot } from "./ui/primitives";

interface HeaderProps {
  health: HealthState;
  onRefreshHealth: () => void;
  onOpenCapabilities: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

const HEALTH_LABEL: Record<HealthState, string> = {
  checking: "connecting",
  online: "daemon online",
  offline: "daemon offline",
};

/** Glass-morphism header. `pl-20` clears the macOS traffic lights, which overlay
 *  the content because the window uses an overlay title bar. */
export function Header({ health, onRefreshHealth, onOpenCapabilities, theme, onToggleTheme }: HeaderProps) {
  return (
    <header
      data-tauri-drag-region
      className="sticky top-0 z-50 shrink-0 bg-background/80 backdrop-blur-sm border-b border-border/40"
    >
      <div className="flex items-center justify-between gap-4 px-6 pl-20 py-3.5">
        <div data-tauri-drag-region className="flex items-center gap-3">
          <span className="text-lg font-mono font-medium tracking-tight select-none">[echlon]</span>
          <span className="hidden sm:inline text-xs font-mono text-muted-foreground/70">
            local agent console
          </span>
        </div>

        <nav className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenCapabilities}
            title="Skills & connectors"
            className="flex items-center gap-2 rounded-full border border-border px-3 py-1.5 text-xs font-mono text-muted-foreground transition-colors hover:text-foreground"
          >
            <Icon name="plug" className="w-[14px] h-[14px]" />
            <span className="hidden sm:inline">capabilities</span>
          </button>

          <button
            type="button"
            onClick={onRefreshHealth}
            title="Check daemon connection"
            className={cn(
              "flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-mono transition-colors",
              health === "online"
                ? "border-border text-muted-foreground hover:text-foreground"
                : health === "offline"
                  ? "border-destructive/30 text-destructive/90 hover:text-destructive"
                  : "border-border text-muted-foreground",
            )}
          >
            <LiveDot
              tone={health === "online" ? "emerald" : health === "offline" ? "destructive" : "muted"}
              pulse={health !== "offline"}
            />
            {HEALTH_LABEL[health]}
          </button>

          <motion.button
            type="button"
            onClick={onToggleTheme}
            whileTap={{ scale: 0.92 }}
            title="Toggle theme"
            className="flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition-colors"
          >
            <Icon name={theme === "dark" ? "sun" : "moon"} className="w-[18px] h-[18px]" />
          </motion.button>
        </nav>
      </div>
    </header>
  );
}
