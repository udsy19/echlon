import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  addConnector,
  installSkill,
  listConnectors,
  listSkills,
  removeConnector,
} from "../lib/daemon";
import type { Connector, Skill } from "../lib/types";
import { Button } from "./ui/Button";
import { Icon } from "./ui/Icon";
import { TextInput, Textarea } from "./ui/form";
import { Eyebrow, Spinner } from "./ui/primitives";

interface Props {
  open: boolean;
  onClose: () => void;
  base: string;
}

/** Slide-over for the agent's acquired capabilities: install skills from
 *  skills.sh and configure MCP connectors. */
export function CapabilitiesPanel({ open, onClose, base }: Props) {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [s, c] = await Promise.all([listSkills(base), listConnectors(base)]);
      setSkills(s);
      setConnectors(c);
    } finally {
      setLoading(false);
    }
  }, [base]);

  useEffect(() => {
    if (open) void refresh();
  }, [open, refresh]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-border bg-background shadow-2xl"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
          >
            <header className="flex items-center justify-between border-b border-border/50 px-5 py-4">
              <div className="flex items-center gap-2.5">
                <Icon name="plug" className="w-5 h-5 text-muted-foreground" />
                <h2 className="text-base font-medium">Capabilities</h2>
                {loading && <Spinner className="text-muted-foreground" />}
              </div>
              <button
                type="button"
                onClick={onClose}
                className="flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
              >
                <Icon name="x" className="w-4 h-4" strokeWidth={2} />
              </button>
            </header>

            <div className="flex-1 space-y-8 overflow-y-auto scroll-thin px-5 py-5">
              <SkillsSection base={base} skills={skills} onChanged={refresh} />
              <ConnectorsSection base={base} connectors={connectors} onChanged={refresh} />
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function SkillsSection({ base, skills, onChanged }: { base: string; skills: Skill[]; onChanged: () => void }) {
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function install() {
    if (!source.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      setMsg(await installSkill(base, source.trim()));
      setSource("");
      onChanged();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <Eyebrow uppercase className="mb-3">Skills</Eyebrow>
      <p className="mb-3 text-sm text-muted-foreground">
        Give the agent new know-how. Browse{" "}
        <a href="https://skills.sh" target="_blank" rel="noreferrer" className="text-emerald-500 underline underline-offset-2">
          skills.sh
        </a>{" "}
        and install by <span className="font-mono text-xs">owner/repo</span>.
      </p>
      <div className="mb-3 flex gap-2">
        <TextInput
          compact
          value={source}
          onChange={(e) => setSource(e.currentTarget.value)}
          onKeyDown={(e) => e.key === "Enter" && install()}
          placeholder="vercel-labs/agent-skills"
          spellCheck={false}
          className="flex-1"
        />
        <Button variant="small" onClick={install} disabled={busy || !source.trim()}>
          {busy ? <Spinner /> : "Install"}
        </Button>
      </div>
      {msg && <p className="mb-3 text-xs font-mono text-muted-foreground break-words">{msg}</p>}

      {skills.length === 0 ? (
        <p className="text-sm text-muted-foreground/60">No skills installed yet.</p>
      ) : (
        <ul className="space-y-2">
          {skills.map((s) => (
            <li key={s.name} className="rounded-xl border border-border/60 bg-muted/20 px-3.5 py-2.5">
              <p className="font-mono text-sm">{s.name}</p>
              {s.description && <p className="mt-0.5 text-xs text-muted-foreground">{s.description}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ConnectorsSection({
  base,
  connectors,
  onChanged,
}: {
  base: string;
  connectors: Connector[];
  onChanged: () => void;
}) {
  const [name, setName] = useState("");
  const [spec, setSpec] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function add() {
    if (!name.trim() || !spec.trim()) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(spec);
    } catch {
      setMsg("Spec must be valid JSON.");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      setMsg(await addConnector(base, name.trim(), parsed));
      setName("");
      setSpec("");
      onChanged();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(n: string) {
    await removeConnector(base, n);
    onChanged();
  }

  return (
    <section>
      <Eyebrow uppercase className="mb-3">Connectors (MCP)</Eyebrow>
      <p className="mb-3 text-sm text-muted-foreground">
        Integrations the agent can use (calendar, gmail, github…). Changes apply on the next conversation.
      </p>

      {connectors.length > 0 && (
        <ul className="mb-4 space-y-2">
          {connectors.map((c) => (
            <li key={c.name} className="flex items-center justify-between gap-2 rounded-xl border border-border/60 bg-muted/20 px-3.5 py-2.5">
              <div className="min-w-0">
                <p className="font-mono text-sm">{c.name}{!c.enabled && <span className="ml-2 text-xs text-muted-foreground">(disabled)</span>}</p>
                <p className="truncate text-xs text-muted-foreground">{c.where}</p>
              </div>
              <button
                type="button"
                onClick={() => remove(c.name)}
                title="Remove"
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:text-destructive"
              >
                <Icon name="x" className="w-4 h-4" strokeWidth={2} />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-2">
        <TextInput
          compact
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
          placeholder="connector name (e.g. gcal)"
          spellCheck={false}
        />
        <Textarea
          value={spec}
          onChange={(e) => setSpec(e.currentTarget.value)}
          rows={4}
          spellCheck={false}
          placeholder={'{ "command": "npx", "args": ["-y", "@some/mcp-server"] }'}
          className="font-mono text-xs"
        />
        <Button variant="small" onClick={add} disabled={busy || !name.trim() || !spec.trim()}>
          {busy ? <Spinner /> : "Add connector"}
        </Button>
      </div>
      {msg && <p className="mt-3 text-xs font-mono text-muted-foreground break-words">{msg}</p>}
    </section>
  );
}
