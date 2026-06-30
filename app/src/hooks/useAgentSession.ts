import { useCallback, useMemo, useRef, useState } from "react";
import {
  approve as approveCall,
  cancelTurn,
  closeSession,
  sendMessage,
  startTask,
  streamEvents,
} from "../lib/daemon";
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
  error: string | null;
}

const INITIAL: SessionState = {
  status: "idle",
  sessionId: null,
  events: [],
  pending: [],
  error: null,
};

/** Owns one ongoing conversation with the agent: opens the session on the first
 *  message, keeps the (single, long-lived) event stream, sends follow-up messages
 *  that either start a new turn or steer the running one, and tracks approvals. */
export function useAgentSession(base: string) {
  const [state, setState] = useState<SessionState>(INITIAL);
  const seq = useRef(0);
  const token = useRef(0); // guards stale events from a closed conversation
  const sessionRef = useRef<string | null>(null);

  const ingest = useCallback((tk: number, event: DaemonEvent) => {
    if (tk !== token.current) return;

    if (event.type === "__closed") {
      setState((s) => (s.status === "error" ? s : { ...s, status: "closed" }));
      return;
    }

    setState((s) => {
      const te: TimelineEvent = { ...event, _id: seq.current++, _at: Date.now() };
      const events = [...s.events, te];
      switch (event.type) {
        case "turn_started":
          return { ...s, events, status: "running" };
        case "approval_request":
          return {
            ...s,
            events,
            pending: [...s.pending, { id: event.data.id, summary: event.data.summary }],
            status: "awaiting_approval",
          };
        case "approval_timeout": {
          const pending = s.pending.filter((p) => p.id !== event.data.id);
          return { ...s, events, pending, status: pending.length ? "awaiting_approval" : "running" };
        }
        case "turn_done":
          return { ...s, events, status: s.pending.length ? s.status : "idle" };
        case "closed":
          return { ...s, events, status: "closed" };
        default:
          // plan / tool_call / step / final_answer / error / user_message / started
          return { ...s, events };
      }
    });
  }, []);

  /** Send a message. First message opens the session (using runConfig); later
   *  messages go to the open session, where the daemon starts a new turn (idle)
   *  or steers the running one. */
  const send = useCallback(
    async (text: string, runConfig: RunConfig) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      if (sessionRef.current) {
        const sid = sessionRef.current;
        setState((s) => (s.status === "idle" ? { ...s, status: "running" } : s));
        try {
          await sendMessage(base, sid, trimmed);
        } catch (err) {
          setState((s) => ({ ...s, error: errorMessage(err) }));
        }
        return;
      }

      const tk = ++token.current;
      seq.current = 0;
      setState({ ...INITIAL, status: "starting" });
      try {
        const sid = await startTask(base, { ...runConfig, task: trimmed });
        if (tk !== token.current) return;
        sessionRef.current = sid;
        setState((s) => ({ ...s, sessionId: sid, status: "running" }));
        streamEvents(base, sid, (e) => ingest(tk, e)).catch((err) => {
          if (tk !== token.current) return;
          setState((s) => (s.status === "closed" ? s : { ...s, status: "error", error: String(err) }));
        });
      } catch (err) {
        if (tk !== token.current) return;
        setState((s) => ({ ...s, status: "error", error: errorMessage(err) }));
      }
    },
    [base, ingest],
  );

  const decide = useCallback(
    async (id: string, decision: ApprovalDecision) => {
      const sid = sessionRef.current;
      if (!sid) return;
      const removed = state.pending.find((p) => p.id === id);
      setState((s) => ({
        ...s,
        pending: s.pending.filter((p) => p.id !== id),
        status: s.pending.length > 1 ? "awaiting_approval" : "running",
      }));
      try {
        await approveCall(base, sid, id, decision);
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
    [base, state.pending],
  );

  /** Stop the in-progress turn (the conversation stays open). */
  const cancel = useCallback(async () => {
    const sid = sessionRef.current;
    if (!sid) return;
    try {
      await cancelTurn(base, sid);
    } catch {
      /* best-effort */
    }
  }, [base]);

  /** End this conversation and clear the UI for a fresh one. */
  const newConversation = useCallback(async () => {
    const sid = sessionRef.current;
    token.current++;
    seq.current = 0;
    sessionRef.current = null;
    setState(INITIAL);
    if (sid) {
      try {
        await closeSession(base, sid);
      } catch {
        /* best-effort */
      }
    }
  }, [base]);

  const isBusy = useMemo(
    () => state.status === "starting" || state.status === "running" || state.status === "awaiting_approval",
    [state.status],
  );
  const hasConversation = state.events.length > 0 || state.sessionId !== null;

  return { ...state, isBusy, hasConversation, send, decide, cancel, newConversation };
}

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "Something went wrong talking to the daemon.";
}
