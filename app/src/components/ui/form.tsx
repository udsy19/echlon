import { motion } from "framer-motion";
import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

const FIELD_BASE =
  "w-full bg-background border border-border outline-none transition-all placeholder:text-muted-foreground/40 focus:border-primary/50 focus:ring-2 focus:ring-primary/20 disabled:opacity-50";

/** Pill text input. `compact` for dense settings rows. */
export function TextInput({
  compact = false,
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { compact?: boolean }) {
  return (
    <input
      className={cn(
        FIELD_BASE,
        "rounded-full",
        compact ? "px-4 py-2.5 text-sm" : "px-5 py-4 text-base",
        className,
      )}
      {...rest}
    />
  );
}

/** Rounded-2xl textarea (resize disabled) — the primary task composer field. */
export function Textarea({
  className,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(FIELD_BASE, "rounded-2xl px-5 py-4 text-base resize-none", className)}
      {...rest}
    />
  );
}

export interface SelectOption<T extends string> {
  value: T;
  label: string;
}

/** Grid of single-select buttons (rounded-xl). Selected = primary tint. */
export function SelectButtons<T extends string>({
  options,
  value,
  onChange,
  columns = 3,
}: {
  options: SelectOption<T>[];
  value: T;
  onChange: (value: T) => void;
  columns?: number;
}) {
  return (
    <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
      {options.map((opt) => {
        const selected = opt.value === value;
        return (
          <motion.button
            key={opt.value}
            type="button"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onChange(opt.value)}
            aria-pressed={selected}
            className={cn(
              "px-4 py-3 rounded-xl border text-sm font-medium transition-all",
              selected
                ? "border-primary bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:text-foreground hover:border-border/80",
            )}
          >
            {opt.label}
          </motion.button>
        );
      })}
    </div>
  );
}

/** Label + helper text wrapper for a field. */
export function Field({
  label,
  hint,
  htmlFor,
  children,
}: {
  label: string;
  hint?: string;
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <label htmlFor={htmlFor} className="block text-xs font-mono uppercase tracking-wider text-muted-foreground">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-muted-foreground/70">{hint}</p>}
    </div>
  );
}
