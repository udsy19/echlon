import { useEffect, useMemo, useRef } from "react";
import type { ApprovalDecision, PendingApproval, SessionStatus, TimelineEvent } from "../lib/types";
import { EventRow } from "./EventRow";
import { Icon } from "./ui/Icon";
import { Eyebrow, LiveDot, Spinner } from "./ui/primitives";

interface EventStreamProps {
  events: TimelineEvent[];
  status: SessionStatus;
  pending: PendingApproval[];
  onDecide: (id: string, decision: ApprovalDecision) => void;
}

export function EventStream({ events, status, pending, onDecide }: EventStreamProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinnedToBottom = useRef(true);

  // Track whether the user is reading the latest output; only auto-scroll then.
  function onScroll() {
    const el = scrollRef.current;
    if (!el) return;
    pinnedToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }

  useEffect(() => {
    const el = scrollRef.current;
    if (el && pinnedToBottom.current) el.scrollTop = el.scrollHeight;
  }, [events, pending, status]);

  const pendingIds = useMemo(() => new Set(pending.map((p) => p.id)), [pending]);

  const started = events.find((e) => e.type === "started");
  const timeline = events.filter(
    (e) => e.type !== "started" && e.type !== "done" && e.type !== "__closed",
  );

  if (events.length === 0 && status === "idle") {
    return <EmptyState />;
  }

  return (
    <div ref={scrollRef} onScroll={onScroll} className="h-full overflow-y-auto scroll-thin px-6 pb-6">
      <div className="mx-auto max-w-3xl">
        {started?.type === "started" && (
          <div className="sticky top-0 z-10 -mx-1 mb-4 bg-background/85 backdrop-blur-sm px-1 pt-1 pb-3">
            <Eyebrow uppercase className="mb-1.5">
              task
            </Eyebrow>
            <p className="selectable text-base font-light leading-snug">{started.data.task}</p>
            <p className="mt-1 text-xs font-mono text-muted-foreground/70">{started.data.model}</p>
          </div>
        )}

        <div className="space-y-0">
          {timeline.map((event) => (
            <EventRow
              key={event._id}
              event={event}
              isPending={event.type === "approval_request" && pendingIds.has(event.data.id)}
              onDecide={onDecide}
            />
          ))}
        </div>

        <StreamFooter status={status} hasPending={pending.length > 0} />
      </div>
    </div>
  );
}

function StreamFooter({ status, hasPending }: { status: SessionStatus; hasPending: boolean }) {
  if (status === "awaiting_approval" || hasPending) {
    return (
      <Footer>
        <LiveDot tone="destructive" />
        <span className="text-muted-foreground">Waiting for your approval…</span>
      </Footer>
    );
  }
  if (status === "running" || status === "starting") {
    return (
      <Footer>
        <Spinner className="text-muted-foreground" />
        <span className="text-muted-foreground">The agent is working…</span>
      </Footer>
    );
  }
  if (status === "done") {
    return (
      <Footer>
        <Icon name="check" className="w-4 h-4 text-emerald-500" strokeWidth={2} />
        <span className="text-muted-foreground">Session complete.</span>
      </Footer>
    );
  }
  if (status === "error") {
    return (
      <Footer>
        <Icon name="alert" className="w-4 h-4 text-destructive" strokeWidth={2} />
        <span className="text-destructive">Session ended with an error.</span>
      </Footer>
    );
  }
  return null;
}

function Footer({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2.5 py-5 text-sm font-mono">
      {children}
    </div>
  );
}

/** Calm idle state shown before the first task — restrained, monochrome. */
function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-foreground/5">
        <Icon name="spark" className="w-6 h-6 text-muted-foreground" />
      </div>
      <h2 className="mb-3 text-2xl md:text-3xl font-light tracking-tight">
        Give echlon something to do.
      </h2>
      <p className="max-w-md text-sm leading-relaxed text-muted-foreground">
        Describe a task and the agent will plan, act on your machine, and report back —
        pausing for your approval before anything risky. The full run streams here, step by step.
      </p>
    </div>
  );
}
