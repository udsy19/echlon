import { motion } from "framer-motion";
import { isTauri } from "../lib/daemon";
import { Icon } from "./ui/Icon";

/** Shown when the daemon is unreachable. Distinguishes "not running in the
 *  desktop app at all" from "daemon process is down", and tells the user how to
 *  fix each. */
export function ConnectionNotice({ base, onRetry }: { base: string; onRetry: () => void }) {
  const browser = !isTauri();
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-6 mt-4 rounded-2xl border border-destructive/30 bg-destructive/5 px-5 py-4"
    >
      <div className="flex items-start gap-3">
        <Icon name="plug" className="mt-0.5 w-5 h-5 text-destructive" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">
            {browser ? "Open the desktop app" : "Can’t reach the echlon daemon"}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            {browser ? (
              <>The backend is only reachable from the Tauri shell. Run <Code>pnpm tauri dev</Code>.</>
            ) : (
              <>
                Start it with <Code>uv run echlon serve</Code>, then retry. Expected at{" "}
                <Code>{base}</Code>.
              </>
            )}
          </p>
        </div>
        {!browser && (
          <button
            type="button"
            onClick={onRetry}
            className="flex shrink-0 items-center gap-1.5 rounded-full border border-border px-3.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground hover:border-foreground/30"
          >
            <Icon name="refresh" className="w-3.5 h-3.5" strokeWidth={2} />
            Retry
          </button>
        )}
      </div>
    </motion.div>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="selectable rounded-md border border-border/60 bg-foreground/5 px-1.5 py-0.5 font-mono text-xs">
      {children}
    </code>
  );
}
