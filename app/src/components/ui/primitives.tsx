import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

/** Monospace eyebrow / section label (sentence-case in main use, uppercase for
 *  small structural labels). */
export function Eyebrow({
  children,
  uppercase = false,
  className,
}: {
  children: ReactNode;
  uppercase?: boolean;
  className?: string;
}) {
  return (
    <p
      className={cn(
        "font-mono text-muted-foreground",
        uppercase ? "text-xs uppercase tracking-wider" : "text-sm",
        className,
      )}
    >
      {children}
    </p>
  );
}

/** Card: rounded-2xl, 1px border, background fill — never a colored card body. */
export function Card({
  children,
  className,
  highlighted = false,
}: {
  children: ReactNode;
  className?: string;
  highlighted?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border bg-background",
        highlighted ? "border-foreground/20 bg-foreground/5" : "border-border",
        className,
      )}
    >
      {children}
    </div>
  );
}

type DotTone = "emerald" | "muted" | "destructive";

const DOT_COLOR: Record<DotTone, string> = {
  emerald: "bg-emerald-500",
  muted: "bg-muted-foreground",
  destructive: "bg-destructive",
};

/** Pulsing status dot. Pulses only while `pulse` (e.g. a live/running state). */
export function LiveDot({ tone = "emerald", pulse = true }: { tone?: DotTone; pulse?: boolean }) {
  return (
    <motion.span
      className={cn("inline-block w-2 h-2 rounded-full", DOT_COLOR[tone])}
      animate={pulse ? { scale: [1, 1.25, 1], opacity: [1, 0.7, 1] } : { scale: 1, opacity: 1 }}
      transition={pulse ? { duration: 2, repeat: Infinity } : { duration: 0.2 }}
    />
  );
}

/** Linear spinner (border-trick) for inline loading. */
export function Spinner({ className }: { className?: string }) {
  return (
    <motion.span
      className={cn("inline-block w-4 h-4 rounded-full border-2 border-current border-t-transparent", className)}
      animate={{ rotate: 360 }}
      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
    />
  );
}
