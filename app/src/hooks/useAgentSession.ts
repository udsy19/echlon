import { useCallback, useMemo, useRef, useState } from "react";
import { approve as approveCall, startTask, streamEvents } from "../lib/daemon";
import type {
  ApprovalDecision,
  DaemonEvent,
  PendingApproval,
  RunConfig,
  SessionStatus,
  TimelineEvent,
} from "../lib/types";

interface SessionState {
  status: SessionStatus;
  sessionId: string | null;
  events: TimelineEvent[];
  pending: PendingApproval[];
  finalAnswer: string | null;
  error: string | null;
}

const INITIAL: SessionState = {
  status: "idle",
  sessionId: null,
  events: [],
  pending: [],
  finalAnswer: null,
  error: null,
};

/** Owns one agent run: starts the task, consumes the event stream, tracks
 *  pending approvals, and derives a single status the UI renders from. */
export function useAgentSession(base: string) {
  const [state, setState] = useState<SessionState>(INITIAL);
  const seq = useRef(0);
  // Guards against late events from a previous run landing in a new one.
  const runToken = useRef(0);

  const ingest = useCallback((token: number, event: DaemonEvent) => {
    if (token !== runToken.current) return;

    if (event.type === "__closed") {
      setState((s) =>
        // Only settle to "done" if the run hadn't already errored or finished.
        s.status === "error" || s.status === "done"
          ? s
          : { ...s, status: s.pending.length ? s.status : "done" },
      );
      return;
    }

    setState((s) => {
      const timelineEvent: TimelineEvent = { ...event, _id: seq.current++, _at: Date.now() };
      const events = [...s.events, timelineEvent];

      switch (event.type) {
        case "approval_request":
          return {
            ...s,
            events,
            pending: [...s.pending, { id: event.data.id, summary: event.data.summary }],
            status: "awaiting_approval",
          };
        case "approval_timeout": {
          // The daemon timed the request out (treated as deny); drop the prompt
          // so the UI doesn't stay stuck waiting on an answer it can't give.
          const pending = s.pending.filter((p) => p.id !== event.data.id);
          return { ...s, events, pending, status: pending.length ? "awaiting_approval" : "running" };
        }
        case "final_answer":
          return { ...s, events, finalAnswer: event.data.output };
        case "error":
          return { ...s, events, error: event.data.message, status: "error" };
        case "done":
          return { ...s, events, status: s.pending.length ? s.status : "done" };
        default:
          // Any forward progress clears the "awaiting" state if nothing is pending.
          return {
            ...s,
            events,
            status: s.pending.length ? s.status : "running",
          };
      }
    });
  }, []);

  const run = useCallback(
    async (config: RunConfig) => {
      const token = ++runToken.current;
      seq.current = 0;
      setState({ ...INITIAL, status: "starting" });
      try {
        const sessionId = await startTask(base, config);
        if (token !== runToken.current) return;
        setState((s) => ({ ...s, sessionId, status: "running" }));
        streamEvents(base, sessionId, (event) => ingest(token, event)).catch((err) => {
          if (token !== runToken.current) return;
          setState((s) =>
            s.status === "done" || s.status === "error"
              ? s
              : { ...s, status: "error", error: String(err) },
          );
        });
      } catch (err) {
        if (token !== runToken.current) return;
        setState((s) => ({ ...s, status: "error", error: errorMessage(err) }));
      }
    },
    [base, ingest],
  );

  const decide = useCallback(
    async (id: string, decision: ApprovalDecision) => {
      const sessionId = state.sessionId;
      if (!sessionId) return;
      // Optimistically remove the prompt; restore it if the call fails.
      const removed = state.pending.find((p) => p.id === id);
      setState((s) => ({
        ...s,
        pending: s.pending.filter((p) => p.id !== id),
        status: s.pending.length > 1 ? "awaiting_approval" : "running",
      }));
      try {
        await approveCall(base, sessionId, id, decision);
      } catch (err) {
        if (removed) {
          setState((s) => ({
            ...s,
            pending: [...s.pending, removed],
            status: "awaiting_approval",
            error: errorMessage(err),
          }));
        }
      }
    },
    [base, state.sessionId, state.pending],
  );

  /** Abandon the current run locally (the daemon keeps going; this just detaches
   *  the UI so a fresh task can be composed). */
  const reset = useCallback(() => {
    runToken.current++;
    seq.current = 0;
    setState(INITIAL);
  }, []);

  const isBusy = useMemo(
    () => state.status === "starting" || state.status === "running" || state.status === "awaiting_approval",
    [state.status],
  );

  return { ...state, isBusy, run, decide, reset };
}

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "Something went wrong talking to the daemon.";
}
