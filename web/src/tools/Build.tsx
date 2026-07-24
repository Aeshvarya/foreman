import { useState } from "react";
import { FileStack, AlertTriangle, Loader2 } from "lucide-react";
import { api, type BuildResult } from "../lib/api";
import { GlassCard, Button, Badge, Kicker } from "../components/primitives";
import { cn } from "../lib/cn";

export default function Build() {
  const [res, setRes] = useState<BuildResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try { setRes(await api.buildGraph()); } catch { /* ignore */ }
    setLoading(false);
  }

  return (
    <div className="mx-auto max-w-[900px]">
      <p className="mb-6 max-w-2xl text-sm leading-relaxed text-muted">
        Foreman doesn't need clean data. It reads the messy documents a real project
        generates — POs, supplier emails, GPS feeds, goods-received notes, submittal logs —
        and builds the confidence-scored knowledge graph itself, scoring every fact by how
        trustworthy its source is and flagging conflicts when documents disagree.
      </p>

      <Button onClick={run}>
        {loading ? <><Loader2 size={16} className="animate-spin" /> reading documents…</> : <><FileStack size={16} /> Build graph from documents</>}
      </Button>

      {res && (
        <div className="mt-8">
          <div className="grid grid-cols-3 gap-3">
            {[[res.docs, "documents read"], [res.facts, "facts extracted"],
              [res.conflicts.length, "conflicts caught", res.conflicts.length > 0]].map(([v, l, hot]) => (
              <GlassCard key={l as string} className="p-5">
                <div className={cn("font-display text-3xl font-bold", hot ? "text-red" : "text-text")}>{v as number}</div>
                <div className="kicker mt-1.5">{l as string}</div>
              </GlassCard>
            ))}
          </div>

          {res.conflicts.map((c, i) => (
            <GlassCard key={i} className="mt-4 flex items-start gap-3 border-red/30 p-5">
              <AlertTriangle size={20} className="mt-0.5 shrink-0 text-red" />
              <div className="text-sm">
                <b>Conflict on {c.material} · {c.attribute}</b>
                <div className="mt-1 text-muted">
                  kept <b className="text-text">{c.kept.value}</b> ({c.kept.source}) over{" "}
                  <b className="text-text">{c.rejected[0].value}</b> ({c.rejected[0].source}) →
                  confidence lowered to <b className="text-amber">{Math.round(c.confidence * 100)}%</b> and flagged for human check
                </div>
              </div>
            </GlassCard>
          ))}

          <Kicker className="mb-3 mt-8">Confidence built from source evidence</Kicker>
          <div className="flex flex-col gap-2.5">
            {Object.entries(res.materials).sort().map(([mid, m]) => {
              const pct = Math.round(m.confidence * 100);
              const col = pct < 70 ? "var(--red)" : pct < 85 ? "var(--amber)" : "var(--green)";
              return (
                <GlassCard key={mid} className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="font-display font-bold">
                      {mid} <span className="font-sans text-sm font-normal text-muted">· {pct}% confidence</span>
                      {m.conflict && <span className="ml-2"><Badge tone="red">conflict</Badge></span>}
                    </div>
                  </div>
                  <div className="mt-1 text-xs text-faint">{m.confidence_source}</div>
                  <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-white/5">
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: col }} />
                  </div>
                </GlassCard>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
