import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "../../lib/cn";

/** Renders agent markdown (final answers, plans) as formatted text instead of
 *  raw `**`/backtick source. Element styling is inlined so it matches the app's
 *  design and needs no Tailwind typography plugin. */

const components: Components = {
  p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0 leading-relaxed">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer"
       className="text-emerald-500 underline underline-offset-2 hover:text-emerald-400">
      {children}
    </a>
  ),
  ul: ({ children }) => <ul className="my-2 ml-5 list-disc space-y-1 marker:text-muted-foreground/60">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 ml-5 list-decimal space-y-1 marker:text-muted-foreground/60">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  h1: ({ children }) => <h1 className="mt-3 mb-2 text-lg font-semibold">{children}</h1>,
  h2: ({ children }) => <h2 className="mt-3 mb-2 text-base font-semibold">{children}</h2>,
  h3: ({ children }) => <h3 className="mt-3 mb-1.5 text-sm font-semibold uppercase tracking-wide text-muted-foreground">{children}</h3>,
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-border pl-3 text-muted-foreground">{children}</blockquote>
  ),
  hr: () => <hr className="my-3 border-border/60" />,
  code: ({ className, children }) => {
    // Fenced blocks carry a language- class; inline code does not.
    const isBlock = /language-/.test(className ?? "");
    if (isBlock) {
      return (
        <code className="block overflow-x-auto scroll-thin rounded-lg border border-border/60 bg-muted/40 p-3 font-mono text-xs leading-relaxed">
          {children}
        </code>
      );
    }
    return (
      <code className="rounded bg-muted/60 px-1.5 py-0.5 font-mono text-[0.85em] text-foreground">
        {children}
      </code>
    );
  },
  pre: ({ children }) => <pre className="my-2 whitespace-pre-wrap break-words">{children}</pre>,
};

export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("selectable text-sm", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
