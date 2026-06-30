import { useCallback, useEffect, useRef, useState } from "react";
import { checkHealth, isTauri } from "../lib/daemon";

export type HealthState = "checking" | "online" | "offline";

/** Polls `GET /health` so the UI can show whether the daemon is reachable, and
 *  exposes a manual refresh. Polls slowly (5s) — this is a status light, not a
 *  hot path. */
export function useDaemonHealth(base: string, intervalMs = 5000) {
  const [state, setState] = useState<HealthState>("checking");
  const cancelled = useRef(false);

  const refresh = useCallback(async () => {
    if (!isTauri()) {
      setState("offline");
      return;
    }
    setState((prev) => (prev === "online" ? prev : "checking"));
    const ok = await checkHealth(base);
    if (!cancelled.current) setState(ok ? "online" : "offline");
  }, [base]);

  useEffect(() => {
    cancelled.current = false;
    void refresh();
    const id = setInterval(() => void refresh(), intervalMs);
    return () => {
      cancelled.current = true;
      clearInterval(id);
    };
  }, [refresh, intervalMs]);

  return { state, refresh };
}
