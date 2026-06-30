import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { ApprovalDecision, TimelineEvent } from "../lib/types";
import { cn } from "../lib/cn";
import { EventRow } from "./EventRow";
import { Markdown } from "./ui/Markdown";
import { ApprovalPrompt } from "./ApprovalPrompt";
import { Icon, type IconName } from "./ui/Icon";
import { Spinner } from "./ui/primitives";

interface AgentTurnProps {
  events: TimelineEvent[];
  live: boolean;
  pendingIds: Set<string>;
  onDecide: (id: string, decision: ApprovalDecision) => void;
}

/** Plain-language label + glyph for a technical event, for the friendly view. */
function friendly(ev: TimelineEvent): { icon: IconName; text: string } {
  if (ev.type === "tool_call") {
    const n = ev.data.name;
    if (n.startsWith("shell")) return { icon: "terminal", text: "Running a command" };
    if (n.startsWith("file")) return { icon: "file", text: "Working with files" };
    if (n.startsWith("browser")) return { icon: "globe", text: "Browsing the web" };
    if (n.startsWith("computer")) return { icon: "spark", text: "Using the screen" };
    if (n.startsWith("todo")) return { icon: "list", text: "Updating the plan" };
    return { icon: "spark", text: n };
  }
  if (ev.type === "plan") return { icon: "list", text: "Thinking through a plan" };
  if (ev.type === "step") return { icon: "check", text: "Working through a step" };
  if (ev.type === "error") return { icon: "alert", text: "Hit an error — adapting" };
  if (ev.type === "approval_timeout") return { icon: "shield", text: "Approval timed out" };
  return { icon: "spark", text: "Working" };
}

export function AgentTurn({ events, live, pendingIds, onDecide }: AgentTurnProps) {
  const [open, setOpen] = useState(false);

  const answer = [...events].reverse().find((e) => e.type === "final_answer");
  const approvals = events.filter((e) => e.type === "approval_request");
  const detail = events.filter((e) => e.type !== "final_answer" && e.type !== "approval_request");
  // Friendly one-liner for the most recent action (shown while live).
  const latest = [...detail].reverse().find((e) => ["tool_call", "step", "plan", "error"].includes(e.type));

  return (
    <div className="flex gap-3">
      {/* agent avatar / gutter */}
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-border bg-foreground/5">
        {live ? <Spinner className="text-muted-foreground" /> : <Icon name="spark" className="w-[18px] h-[18px]" />}
      </div>

      <div className="min-w-0 flex-1 space-y-2.5">
        {/* live status line */}
        {live && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            {latest ? (
              <>
                <Icon name={friendly(latest).icon} className="w-4 h-4" />
                <span>{friendly(latest).text}…</span>
              </>
            ) : (
              <span>Getting started…</span>
            )}
          </div>
        )}

        {/* approvals always surface — they need the user */}
        {approvals.map((ev) =>
          ev.type === "approval_request" ? (
            <div key={ev._id} className="rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3">
              <div className="mb-1 flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-destructive">
                <Icon name="shield" className="w-4 h-4" strokeWidth={2} />
                needs your approval
              </div>
              <ApprovalPrompt
                id={ev.data.id}
                summary={ev.data.summary}
                pending={pendingIds.has(ev.data.id)}
                onDecide={onDecide}
              />
            </div>
          ) : null,
        )}

        {/* the answer, rendered as markdown */}
        {answer?.type === "final_answer" && (
          <div className="rounded-2xl border border-border bg-background px-4 py-3">
            <Markdown className="text-[15px]">{answer.data.output}</Markdown>
          </div>
        )}

        {/* expandable technical detail */}
        {detail.length > 0 && (
          <div>
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="flex items-center gap-1.5 text-xs font-mono text-muted-foreground/70 transition-colors hover:text-foreground"
            >
              <motion.span animate={{ rotate: open ? 90 : 0 }} transition={{ duration: 0.2 }}>
                <Icon name="chevron" className="w-3.5 h-3.5 -rotate-90" />
              </motion.span>
              {open ? "Hide details" : `Show details · ${detail.length} step${detail.length === 1 ? "" : "s"}`}
            </button>
            <AnimatePresence initial={false}>
              {open && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className={cn("overflow-hidden")}
                >
                  <div className="mt-2 space-y-0 border-l border-border/50 pl-3">
                    {detail.map((ev) => (
                      <EventRow key={ev._id} event={ev} isPending={false} onDecide={onDecide} />
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}
