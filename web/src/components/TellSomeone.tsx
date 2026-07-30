import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Copy, Check, Printer, HardHat, Briefcase } from "lucide-react";
import { api, type Messages } from "../lib/api";
import { GlassCard, Kicker, Badge } from "./primitives";
import { cn } from "../lib/cn";

/* The last mile: the messages someone actually has to send.
 *
 * Good analysis dies here. Writing to a supplier is awkward and writing to a
 * client is political, so both get postponed until the problem is undeniable —
 * by which point the cheap fixes have expired. Drafting them removes the
 * excuse: copy, read it once, send. */

export default function TellSomeone({ delays }: { delays: Record<string, number> }) {
  const [msgs, setMsgs] = useState<Messages | null>(null);
  const [tab, setTab] = useState<"supplier" | "client">("supplier");
  const [copied, setCopied] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (Object.keys(delays).length === 0) { setMsgs(null); return; }
    let live = true;
    api.messages(delays).then((m) => live && setMsgs(m)).catch(() => live && setMsgs(null));
    return () => { live = false; };
  }, [JSON.stringify(delays)]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!msgs || msgs.empty) return null;
  const active = tab === "supplier" ? msgs.supplier : msgs.client;

  async function copy() {
    if (!active) return;
    await navigator.clipboard.writeText(`Subject: ${active.subject}\n\n${active.body}`);
    setCopied(true); setTimeout(() => setCopied(false), 1800);
  }

  return (
    <GlassCard className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-amber">
            <Send size={15} /><span className="kicker !text-amber/90">Tell someone</span>
          </div>
          <p className="mt-1.5 text-sm text-muted">
            Written for you, with the real dates and numbers already in them.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => window.print()}
            className="flex items-center gap-1.5 rounded-lg border border-line-strong px-3 py-2 text-sm
              transition hover:border-amber/50 hover:text-amber">
            <Printer size={14} /> One-page update
          </button>
          <button onClick={() => setOpen((o) => !o)}
            className="rounded-lg bg-amber px-4 py-2 text-sm font-medium text-black transition hover:bg-amber-bright">
            {open ? "Hide" : "Show me the messages"}
          </button>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="mt-4 flex gap-2">
              {([["supplier", HardHat, "To the supplier"], ["client", Briefcase, "To the client"]] as const)
                .map(([k, Icon, label]) => (
                  <button key={k} onClick={() => setTab(k)}
                    className={cn("flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition",
                      tab === k ? "border-amber/40 bg-amber/10 text-amber"
                        : "border-line text-muted hover:text-text")}>
                    <Icon size={14} /> {label}
                  </button>
                ))}
            </div>

            {active && (
              <div className="mt-3 rounded-xl border border-line bg-black/30 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
                  <div className="min-w-0">
                    <div className="text-xs text-faint">To</div>
                    <div className="truncate text-sm text-text">{active.to}</div>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs text-faint">Subject</div>
                    <div className="truncate text-sm text-text">{active.subject}</div>
                  </div>
                  <button onClick={copy}
                    className="flex shrink-0 items-center gap-1.5 rounded-lg border border-line-strong px-3 py-1.5
                      text-xs transition hover:border-amber/50 hover:text-amber">
                    {copied ? <><Check size={13} /> copied</> : <><Copy size={13} /> copy</>}
                  </button>
                </div>
                <pre className="mt-3 whitespace-pre-wrap font-sans text-sm leading-relaxed text-muted">
                  {active.body}
                </pre>
              </div>
            )}

            <p className="mt-3 flex items-center gap-2 text-xs text-faint">
              <Badge tone="steel">read it first</Badge>
              These are drafts, not sent mail — nothing leaves this screen until you paste it.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </GlassCard>
  );
}
