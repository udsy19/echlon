import { motion, type HTMLMotionProps } from "framer-motion";
import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

type Variant = "primary" | "small" | "secondary" | "ghost" | "danger";

interface ButtonProps extends Omit<HTMLMotionProps<"button">, "ref" | "children"> {
  variant?: Variant;
  children?: ReactNode;
}

/** Buttons per the design system: pills (`rounded-full`) always, `font-medium`,
 *  subtle scale on hover/tap. Primary is the inverted solid (`bg-foreground
 *  text-background`) with a slide-in fill; ghosts are text-only. */
export function Button({ variant = "primary", className, children, disabled, ...rest }: ButtonProps) {
  const base = "rounded-full font-medium transition-colors disabled:opacity-50 disabled:cursor-default";

  if (variant === "ghost" || variant === "danger") {
    return (
      <motion.button
        whileHover={disabled ? undefined : { x: 4 }}
        whileTap={disabled ? undefined : { scale: 0.98 }}
        disabled={disabled}
        className={cn(
          base,
          "px-4 py-2 text-sm flex items-center gap-2",
          variant === "danger"
            ? "text-muted-foreground hover:text-destructive"
            : "text-muted-foreground hover:text-foreground",
          className,
        )}
        {...rest}
      >
        {children}
      </motion.button>
    );
  }

  // Solid, inverted variants with a slide-in fill on hover.
  const sizing =
    variant === "small" ? "text-sm px-4 py-2" : variant === "secondary" ? "px-6 py-3" : "px-8 py-4 text-lg";

  return (
    <motion.button
      whileHover={disabled ? undefined : { scale: 1.02 }}
      whileTap={disabled ? undefined : { scale: 0.98 }}
      disabled={disabled}
      className={cn(
        base,
        sizing,
        "relative overflow-hidden bg-foreground text-background flex items-center justify-center gap-2",
        className,
      )}
      {...rest}
    >
      <span className="relative z-10 flex items-center gap-2">{children}</span>
      {!disabled && (
        <motion.span
          aria-hidden
          className="absolute inset-0 bg-primary"
          initial={{ x: "-101%" }}
          whileHover={{ x: 0 }}
          transition={{ duration: 0.3 }}
        />
      )}
    </motion.button>
  );
}
