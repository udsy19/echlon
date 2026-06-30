import { cn } from "../../lib/cn";

/** Inline stroke icons (24×24, currentColor) per the design system — no icon
 *  library. Default strokeWidth 1.5; check/x/arrows use 2. */

const PATHS = {
  // navigation / actions
  arrowRight: "M13 7l5 5m0 0l-5 5m5-5H6",
  send: "M6 12L3.27 3.5a.6.6 0 01.82-.72l16.2 8.04a.6.6 0 010 1.07L4.09 19.97a.6.6 0 01-.82-.72L6 12zm0 0h7",
  check: "M5 13l4 4L19 7",
  x: "M6 18L18 6M6 6l12 12",
  stop: "M6 6h12v12H6z",
  refresh: "M4 4v5h5M20 20v-5h-5M5.5 9a7.5 7.5 0 0113 -3.5L20 9M18.5 15a7.5 7.5 0 01-13 3.5L4 15",
  // domain glyphs for tool calls
  terminal: "M5 7l5 5-5 5M13 17h6",
  file: "M14 3v4a1 1 0 001 1h4M5 8a2 2 0 012-2h6l6 6v8a2 2 0 01-2 2H7a2 2 0 01-2-2V8z",
  globe: "M3 12h18M12 3a15 15 0 010 18M12 3a15 15 0 000 18M3 12a9 9 0 1018 0 9 9 0 00-18 0z",
  search: "M21 21l-4.3-4.3M11 18a7 7 0 100-14 7 7 0 000 14z",
  code: "M8 9l-3 3 3 3M16 9l3 3-3 3M13 6l-2 12",
  list: "M9 6h11M9 12h11M9 18h11M5 6h.01M5 12h.01M5 18h.01",
  message: "M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z",
  // status / meta
  shield: "M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z",
  spark: "M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18",
  sun: "M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6L4.2 4.2M19.8 19.8l-1.4-1.4M18.4 5.6l1.4-1.4M4.2 19.8l1.4-1.4M12 17a5 5 0 100-10 5 5 0 000 10z",
  moon: "M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z",
  dot: "M12 12h.01",
  alert: "M12 9v4m0 4h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L14.7 3.9a2 2 0 00-3.4 0z",
  chevron: "M6 9l6 6 6-6",
  plug: "M9 7V3M15 7V3M6 7h12v4a6 6 0 01-12 0V7zM12 17v4",
} as const;

export type IconName = keyof typeof PATHS;

interface IconProps {
  name: IconName;
  className?: string;
  strokeWidth?: number;
}

export function Icon({ name, className, strokeWidth = 1.5 }: IconProps) {
  return (
    <svg
      className={cn("w-5 h-5 shrink-0", className)}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={strokeWidth}
        d={PATHS[name]}
      />
    </svg>
  );
}
