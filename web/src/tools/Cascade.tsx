import { useEffect, useState } from "react";
import { AlertTriangle, ShieldCheck, Wrench, Truck } from "lucide-react";
import { api, type Material, type CascadeReport, type AltSupplier } from "../lib/api";
import { useProject } from "../lib/useProject";
import GraphCanvas from "../components/GraphCanvas";
import { GlassCard, Badge, Kicker } from "../components/primitives";
import { cn } from "../lib/cn";

export default function Cascade() {
  const { project } = useProject();
  const [materials, setMaterials] = useState<Material[]>([]);
  const [matId, setMatId] = useState("MAT-1");
  const [delay, setDelay] = useState(5);
  const [report, setReport] = useState<CascadeReport | null>(null);
  const [alt, setAlt] = useState<AltSupplier | null>(null);

  useEffect(() => { api.materials().then((m) => { setMaterials(m); }); }, []);

  useEffect(() => {
    let live = true;
    api.cascade(matId, delay).then((r) => { if (live) setReport(r); });
    return () => { live = false; };
  }, [matId, delay]);

  useEffect(() => {
    if (report && report.handover_slip_days > 0) api.altSupplier(matId).then(setAlt);
    else setAlt(null);
  }, [report, matId]);

  const breaks = !!report && report.handover_slip_days > 0;
  const slippedIds = new Set(report?.slipped.map((s) => s.activity) ?? []);
  const feasibleAlts = alt?.alternates.filter((a) => a.meets_roj) ?? [];

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      {/* -------- left: controls + graph -------- */}
      <div className="flex flex-col gap-5">
        <GlassCard className="flex flex-wrap items-end gap-6 p-5">
          <label className="flex-1 min-w-[220px]">
            <div className="kicker mb-2">Which material slips?</div>
            <select value={matId} onChange={(e) => setMatId(e.target.value)}
              className="w-full rounded-lg border border-line bg-black/30 px-3 py-2.5 text-sm outline-none focus:border-amber/50">
              {materials.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.id})</option>)}
            </select>
          </label>
          <label className="flex-1 min-w-[220px]">
            <div className="kicker mb-2">By how many days? <span className="text-amber">{delay}d</span></div>
            <input type="range" min={1} max={30} value={delay} onChange={(e) => setDelay(+e.target.value)}
              className="w-full" style={{ accentColor: "var(--amber)" }} />
          </label>
        </GlassCard>

        {report && (
          <GlassCard className={cn("flex items-center gap-4 p-5", breaks ? "border-red/40" : "border-green/30")}>
            <div className={breaks ? "text-red" : "text-green"}>
              {breaks ? <AlertTriangle size={26} /> : <ShieldCheck size={26} />}
            </div>
            <div>
              <div className="font-display text-xl font-bold">
                {breaks
                  ? <>Handover breaks — <span className="text-red">+{report.handover_slip_days} days</span></>
                  : <>Handover holds — <span className="text-green">float absorbs it</span></>}
              </div>
              <div className="mt-0.5 text-sm text-muted">
                {report.baseline_handover} {breaks && <>→ <span className="text-text">{report.handover_date}</span></>}
                {" · "}status confidence <b className="text-text">{Math.round(report.confidence * 100)}%</b>
                <span className="text-faint"> ({report.confidence_source})</span>
              </div>
            </div>
          </GlassCard>
        )}

        {project && (
          <GraphCanvas project={project} delayedId={matId} slippedIds={slippedIds} handoverBreaks={breaks} />
        )}
      </div>

      {/* -------- right: details -------- */}
      <div className="flex flex-col gap-4">
        {report && (
          <>
            <GlassCard className="p-5">
              <Kicker className="mb-3">Activities that slip · {report.slipped.length}</Kicker>
              {report.slipped.length === 0
                ? <div className="text-sm text-muted">None — schedule float absorbs the delay.</div>
                : <div className="flex flex-col gap-2">
                    {report.slipped.map((s) => (
                      <div key={s.activity} className="flex items-center justify-between text-sm">
                        <span><b className="font-mono text-red">{s.activity}</b> <span className="text-muted">{s.name}</span></span>
                        <span className="font-mono text-xs text-faint">+{s.slip_days}d</span>
                      </div>
                    ))}
                  </div>}
              {report.absorbed.length > 0 && (
                <div className="mt-3 border-t border-line pt-3 text-xs text-muted">
                  <span className="text-green">{report.absorbed.length}</span> absorbed by float:{" "}
                  <span className="font-mono text-faint">{report.absorbed.map((a) => a.activity).join(", ")}</span>
                </div>
              )}
            </GlassCard>

            <GlassCard className="border-amber/20 p-5">
              <div className="mb-2 flex items-center gap-2"><Wrench size={15} className="text-amber" /><span className="kicker">Mitigation</span></div>
              <p className="text-sm leading-relaxed text-muted">{report.mitigation}</p>
            </GlassCard>

            {breaks && feasibleAlts.length > 0 && (
              <GlassCard className="border-amber/20 p-5">
                <div className="mb-3 flex items-center gap-2"><Truck size={15} className="text-amber" />
                  <span className="kicker">Alternate supply · {alt?.days_to_roj}d to ROJ</span></div>
                <div className="mb-3 text-xs text-muted">A full re-order is too slow — these bridge options still hit the date:</div>
                <div className="flex flex-col gap-2">
                  {feasibleAlts.map((a) => (
                    <div key={a.id} className="flex items-center justify-between text-sm">
                      <span className="text-text">{a.name}</span>
                      <span className="flex items-center gap-2 text-xs text-faint">
                        {a.lead_days}d · {Math.round(a.reliability * 100)}% <Badge tone="green">meets ROJ</Badge>
                      </span>
                    </div>
                  ))}
                </div>
              </GlassCard>
            )}
          </>
        )}
      </div>
    </div>
  );
}
