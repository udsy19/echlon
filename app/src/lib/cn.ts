/** Join class names, dropping falsy values. Intentionally tiny — this UI uses a
 *  fixed, hand-written set of classes, so a full clsx/tailwind-merge isn't
 *  warranted. */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
