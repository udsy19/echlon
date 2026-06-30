import { Button } from "./ui/Button";
import { Icon } from "./ui/Icon";
import type { ApprovalDecision } from "../lib/types";

interface ApprovalPromptProps {
  id: string;
  summary: string;
  pending: boolean;
  onDecide: (id: string, decision: ApprovalDecision) => void;
}

/** The risky-action consent prompt. While `pending`, offers once / always /
 *  deny; once answered it collapses to a neutral "resolved" line. */
export function ApprovalPrompt({ id, summary, pending, onDecide }: ApprovalPromptProps) {
  return (
    <div>
      <p className="selectable text-sm leading-relaxed">{summary}</p>

      {pending ? (
        <div className="mt-3 flex flex-wrap items-center gap-2.5">
          <Button variant="small" onClick={() => onDecide(id, "once")}>
            <Icon name="check" className="w-4 h-4" strokeWidth={2} />
            Allow once
          </Button>
          <button
            type="button"
            onClick={() => onDecide(id, "always")}
            className="rounded-full border border-border px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground hover:border-foreground/30"
          >
            Always allow
          </button>
          <Button variant="danger" onClick={() => onDecide(id, "deny")}>
            <Icon name="x" className="w-4 h-4" strokeWidth={2} />
            Deny
          </Button>
        </div>
      ) : (
        <p className="mt-2 flex items-center gap-1.5 text-xs font-mono text-muted-foreground/60">
          <Icon name="check" className="w-3.5 h-3.5" strokeWidth={2} />
          resolved
        </p>
      )}
    </div>
  );
}
