import { useEffect, useMemo, useRef } from "react";
import type { ApprovalDecision, PendingApproval, SessionStatus, TimelineEvent } from "../lib/types";
import { AgentTurn } from "./AgentTurn";
import { Icon } from "./ui/Icon";

interface ConversationProps {
  events: TimelineEvent[];
  status: SessionStatus;
  pending: PendingApproval[];
  onDecide: (id: string, decision: ApprovalDecision) => void;
  onExample: (text: string) => void;
}

type Block =
  | { kind: "user"; id: number; text: string }
  | { kind: "turn"; id: number; events: TimelineEvent[] };

/** Fold the flat event stream into a thread of user messages and agent turns. */
function toBlocks(events: TimelineEvent[]): Block[] {
  const blocks: Block[] = [];
  let turn: Extract<Block, { kind: "turn" }> | null = null;
  for (const ev of events) {
    switch (ev.type) {
      case "user_message":
        turn = null;
        blocks.push({ kind: "user", id: ev._id, text: ev.data.text });
        break;
      case "started":
      case "closed":
      case "__closed":
        break;
      case "turn_started":
        turn = { kind: "turn", id: ev._id, events: [] };
        blocks.push(turn);
        break;
      case "turn_done":
        turn = null;
        break;
      default:
        if (!turn) {
          turn = { kind: "turn", id: ev._id, events: [] };
          blocks.push(turn);
        }
        turn.events.push(ev);
    }
  }
  return blocks;
}

export function Conversation({ events, status, pending, onDecide, onExample }: ConversationProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const blocks = useMemo(() => toBlocks(events), [events]);
  const pendingIds = useMemo(() => new Set(pending.map((p) => p.id)), [pending]);

  function onScroll() {
    const el = scrollRef.current;
    if (!el) return;
    pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  }
  useEffect(() => {
    const el = scrollRef.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  }, [events, pending, status]);

  if (events.length === 0) {
    return <EmptyState onExample={onExample} />;
  }

  const liveTurns = status === "running" || status === "awaiting_approval" || status === "starting";
  const lastTurnIdx = blocks.map((b) => b.kind).lastIndexOf("turn");

  return (
    <div ref={scrollRef} onScroll={onScroll} className="h-full overflow-y-auto scroll-thin px-6 pb-4">
      <div className="mx-auto max-w-3xl space-y-6 py-6">
        {blocks.map((block, i) =>
          block.kind === "user" ? (
            <div key={block.id} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md bg-foreground px-4 py-2.5 text-background">
                <p className="selectable whitespace-pre-wrap text-[15px] leading-relaxed">{block.text}</p>
              </div>
            </div>
          ) : (
            <AgentTurn
              key={block.id}
              events={block.events}
              live={liveTurns && i === lastTurnIdx}
              pendingIds={pendingIds}
              onDecide={onDecide}
            />
          ),
        )}
      </div>
    </div>
  );
}

const EXAMPLES = [
  "Organize my Downloads folder by file type",
  "Find the 3 biggest files on my Desktop and tell me what they are",
  "Build a little Python snake game in ~/echlon/workspace and open it",
  "Summarize the top 5 Hacker News stories right now",
];

function EmptyState({ onExample }: { onExample: (text: string) => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-foreground/5">
        <Icon name="spark" className="w-6 h-6 text-muted-foreground" />
      </div>
      <h2 className="mb-3 text-2xl font-light tracking-tight md:text-3xl">What can I do for you?</h2>
      <p className="mb-7 max-w-md text-sm leading-relaxed text-muted-foreground">
        Ask in plain language and I’ll do it on your Mac — files, the web, apps, code.
        I’ll check with you before anything risky, and you can keep chatting to steer me.
      </p>
      <div className="grid w-full max-w-xl gap-2 sm:grid-cols-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => onExample(ex)}
            className="rounded-xl border border-border bg-background px-4 py-3 text-left text-sm text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}
