import { motion } from "framer-motion";
import type { ApprovalDecision, TimelineEvent } from "../lib/types";
import { cn } from "../lib/cn";
import { Icon, type IconName } from "./ui/Icon";
import { ApprovalPrompt } from "./ApprovalPrompt";
import { Markdown } from "./ui/Markdown";

/** Scrollable monospace block for tool arguments / observations / answers. */
function CodeBlock({ text, tone = "default" }: { text: string; tone?: "default" | "error" }) {
  if (!text) return null;
  return (
    <pre
      className={cn(
        "selectable mt-2 max-h-56 overflow-auto scroll-thin rounded-xl border px-3.5 py-3 font-mono text-xs leading-relaxed whitespace-pre-wrap break-words",
        tone === "error"
          ? "border-destructive/30 bg-destructive/5 text-destructive"
          : "border-border/60 bg-muted/30 text-muted-foreground",
      )}
    >
      {text}
    </pre>
  );
}

/** Map a prefixed tool name (`shell_exec`, `file_read`, …) to a glyph. */
function toolIcon(name: string): IconName {
  const prefix = name.split("_")[0];
  switch (prefix) {
    case "shell":
      return "terminal";
    case "file":
      return "file";
    case "browser":
      return "globe";
    case "search":
      return "search";
    case "code":
      return "code";
    case "todo":
      return "list";
    case "message":
      return "message";
    default:
      return "spark";
  }
}

function formatTime(ms: number): string {
  const d = new Date(ms);
  return d.toLocaleTimeString([], { hour12: false });
}

interface Meta {
  icon: IconName;
  label: string;
  accent?: "emerald" | "destructive";
}

interface EventRowProps {
  event: TimelineEvent;
  isPending: boolean;
  onDecide: (id: string, decision: ApprovalDecision) => void;
}

/** Renders one timeline event. `started`/`done`/`__closed` are handled by the
 *  stream itself and never reach here. */
export function EventRow({ event, isPending, onDecide }: EventRowProps) {
  // Approval requests get their own interactive treatment.
  if (event.type === "approval_request") {
    return (
      <Row meta={{ icon: "shield", label: "approval requested", accent: "destructive" }} time={event._at}>
        <ApprovalPrompt
          id={event.data.id}
          summary={event.data.summary}
          pending={isPending}
          onDecide={onDecide}
        />
      </Row>
    );
  }

  switch (event.type) {
    case "plan":
      return (
        <Row meta={{ icon: "list", label: "plan" }} time={event._at}>
          <Markdown className="text-muted-foreground">{event.data.plan}</Markdown>
        </Row>
      );

    case "tool_call":
      return (
        <Row meta={{ icon: toolIcon(event.data.name), label: "tool call" }} time={event._at}>
          <p className="text-sm font-medium">
            <span className="font-mono">{event.data.name}</span>
          </p>
          <CodeBlock text={event.data.arguments} />
        </Row>
      );

    case "step":
      return (
        <Row
          meta={{ icon: event.data.error ? "alert" : "check", label: `step ${event.data.step}`, accent: event.data.error ? "destructive" : undefined }}
          time={event._at}
        >
          {event.data.observations && <CodeBlock text={event.data.observations} />}
          {event.data.error && <CodeBlock text={event.data.error} tone="error" />}
          {!event.data.observations && !event.data.error && (
            <p className="text-sm text-muted-foreground/60">No output.</p>
          )}
        </Row>
      );

    case "final_answer":
      return (
        <Row meta={{ icon: "check", label: "final answer", accent: "emerald" }} time={event._at} highlighted>
          <Markdown className="text-[15px]">{event.data.output}</Markdown>
        </Row>
      );

    case "approval_timeout":
      return (
        <Row meta={{ icon: "shield", label: "approval timed out", accent: "destructive" }} time={event._at}>
          <p className="selectable text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap">
            No response in time — the daemon denied this action and continued.
          </p>
        </Row>
      );

    case "error":
      return (
        <Row meta={{ icon: "alert", label: "error", accent: "destructive" }} time={event._at}>
          <p className="selectable text-sm leading-relaxed text-destructive whitespace-pre-wrap">
            {event.data.message}
          </p>
        </Row>
      );

    default:
      return null;
  }
}

/** Shared row chrome: icon gutter + monospace label + timestamp + body. */
function Row({
  meta,
  time,
  highlighted = false,
  children,
}: {
  meta: Meta;
  time: number;
  highlighted?: boolean;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="flex gap-3.5"
    >
      {/* Icon + connector */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border",
            meta.accent === "emerald"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-500"
              : meta.accent === "destructive"
                ? "border-destructive/30 bg-destructive/10 text-destructive"
                : "border-border bg-foreground/5 text-foreground",
          )}
        >
          <Icon name={meta.icon} className="w-[18px] h-[18px]" strokeWidth={meta.icon === "check" ? 2 : 1.5} />
        </div>
        <div className="mt-1 w-px flex-1 bg-border/50" />
      </div>

      {/* Body */}
      <div
        className={cn(
          "min-w-0 flex-1 rounded-2xl border px-4 py-3 mb-1",
          highlighted ? "border-foreground/20 bg-foreground/5" : "border-border/60 bg-background",
        )}
      >
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">{meta.label}</span>
          <span className="text-[11px] font-mono text-muted-foreground/50 tabular-nums">{formatTime(time)}</span>
        </div>
        <div className="mt-1.5">{children}</div>
      </div>
    </motion.div>
  );
}
