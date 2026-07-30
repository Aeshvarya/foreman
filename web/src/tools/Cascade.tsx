import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertTriangle, ShieldCheck, Truck, X } from "lucide-react";
import { api, type Material, type CascadeReport, type AltSupplier, type CascadeScene } from "../lib/api";
import { useProject } from "../lib/useProject";
import GraphCanvas from "../components/GraphCanvas";
import RecoveryPlan from "../components/RecoveryPlan";
import CostOfWaiting from "../components/CostOfWaiting";
import TellSomeone from "../components/TellSomeone";
import { GlassCard, Badge, Kicker } from "../components/primitives";
import { cn } from "../lib/cn";
import { useTour } from "../features/tour/TourProvider";
import { TourTarget } from "../features/tour/TourTarget";
import { TOURS } from "../features/tour/tours";
import { SCENE_KEY } from "../lib/scene";

const input = "rounded-lg border border-line bg-black/30 px-3 py-2 text-sm outline-none focus:border-amber/50";

/** A percentage makes people nod without understanding. Words don't. Mirrors
 *  the wording the Today brief uses so the app sounds like one voice. */
function sureness(confidence: number): string {
  if (confidence >= 0.9) return "confident";
  if (confidence >= 0.8) return "fairly sure";
  if (confidence >= 0.65) return "not confident";
  return "really not sure";
}

export default function Cascade() {
  const { project } = useProject();
  const [materials, setMaterials] = useState<Material[]>([]);
  // Arriving from a "Try it" button on Today means the user already has a
  // material in mind — open on that one, slipped by the week the brief priced.
  const [search] = useSearchParams();
  const fromBrief = search.get("slip");
  const [delays, setDelays] = useState<Record<string, number>>(
    fromBrief ? { [fromBrief]: 7 } : { "MAT-1": 5 });
  const [debouncedDelays, setDebouncedDelays] = useState(delays);
  const [report, setReport] = useState<CascadeReport | null>(null);
  const [alts, setAlts] = useState<Record<string, AltSupplier>>({});
  const { start, steps: activeTour } = useTour();

  useEffect(() => { api.materials().then(setMaterials); }, []);

  // Dragging a slider fires an onChange on every pixel of mouse movement —
  // tens of updates per second. Feeding that straight into the graph was
  // slamming React Flow with brand-new nodes/edges arrays faster than its
  // internal store could settle, and it would silently start dropping edges
  // (nodes stayed, edges vanished — a real React Flow desync, not a crash).
  // The slider itself still reads/writes the raw `delays` state so it feels
  // instant; only the expensive downstream work (network fetch + graph)
  // waits for a short pause in dragging.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedDelays(delays), 150);
    return () => clearTimeout(t);
  }, [delays]);

  // First-ever visit → spotlight tour, once the first cascade result is in
  // and no other tour (e.g. the shell tour) is still running — re-fires once
  // that clears, so a same-tick race with another tour never drops this one.
  useEffect(() => {
    if (!report || activeTour) return;
    const t = setTimeout(() => start("cascade", TOURS.cascade), 200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [!!report, !!activeTour]);

  // recompute the COMBINED cascade whenever the (debounced) set of delays changes
  useEffect(() => {
    let live = true;
    api.cascadeMulti(debouncedDelays).then((r) => { if (live) setReport(r); }).catch(() => {});
    return () => { live = false; };
  }, [debouncedDelays]);

  const breaks = !!report && report.handover_slip_days > 0;
  // The biggest single slip drives the "cost of waiting" story.
  const worstDelay = Object.entries(debouncedDelays)
    .sort((a, b) => b[1] - a[1])[0] as [string, number] | undefined;

  // These two Sets are GraphCanvas's memo dependencies, so their *identity*
  // decides whether the graph rebuilds. Built inline with `new Set(...)` they
  // were fresh objects on every single render, which invalidated that memo
  // every time and handed React Flow brand-new nodes/edges arrays forever —
  // and under that churn it intermittently dropped every edge (nodes rendered,
  // 0 edges, no error). Keying the memo on a stable string makes the identity
  // change only when the contents actually change.
  const slippedKey = (report?.slipped ?? []).map((s) => s.activity).sort().join(",");
  const delayedKey = Object.keys(debouncedDelays).sort().join(",");
  // The graph reads the debounced set too, so "delayed" (amber) and "slipped"
  // (red) always reflect the SAME point in time — never a half-updated frame.
  const slippedIds = useMemo(
    () => new Set(slippedKey ? slippedKey.split(",") : []), [slippedKey]);
  const delayedIds = useMemo(
    () => new Set(delayedKey ? delayedKey.split(",") : []), [delayedKey]);

  const name = (id: string) => materials.find((m) => m.id === id)?.name ?? id;

  // alternate suppliers for the delayed materials, only when the handover breaks
  useEffect(() => {
    if (!breaks) { setAlts({}); return; }
    let live = true;
    Promise.all(Object.keys(debouncedDelays).map((id) => api.altSupplier(id).then((a) => [id, a] as const)))
      .then((pairs) => { if (live) setAlts(Object.fromEntries(pairs)); });
    return () => { live = false; };
  }, [report, breaks]); // eslint-disable-line react-hooks/exhaustive-deps

  // Publish the live simulator state so any "Ask Foreman" surface (the
  // floating widget or the dedicated tab) can explain what's actually on
  // screen right now instead of re-querying the static graph. Cleared on
  // unmount so it can never be stale-referenced from a different page.
  useEffect(() => {
    if (!report) return;
    const scene: CascadeScene = {
      delayed: Object.entries(debouncedDelays).map(([id, days]) => ({ id, name: name(id), days })),
      handover_breaks: breaks,
      handover_slip_days: report.handover_slip_days,
      baseline_handover: report.baseline_handover,
      new_handover: report.handover_date,
      confidence: report.confidence,
      slipped_activities: report.slipped.map((s) => ({ id: s.activity, name: s.name, slip_days: s.slip_days })),
      absorbed_by_float: report.absorbed.map((s) => s.activity),
      mitigation: report.mitigation,
    };
    try { sessionStorage.setItem(SCENE_KEY, JSON.stringify(scene)); } catch { /* ignore */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report, debouncedDelays, breaks]);

  useEffect(() => () => { try { sessionStorage.removeItem(SCENE_KEY); } catch { /* ignore */ } }, []);

  const toggle = (id: string) => setDelays((d) => {
    const n = { ...d };
    if (id in n) delete n[id]; else n[id] = 7;
    return n;
  });
  const setDelay = (id: string, days: number) => setDelays((d) => ({ ...d, [id]: days }));
  const addable = materials.filter((m) => !(m.id in delays));

  // Slip a whole supplier's order — a supplier usually delays every item at once.
  const suppliers = (project?.nodes ?? []).filter((n) => n.kind === "supplier");
  const addSupplier = (supId: string) => setDelays((d) => {
    const n = { ...d };
    materials.filter((m) => m.supplier === supId).forEach((m) => { if (!(m.id in n)) n[m.id] = 7; });
    return n;
  });

  return (
    <div className="flex flex-col gap-5">
      {/* controls + verdict */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1.15fr]">
        <TourTarget name="cascade-controls">
        <GlassCard className="p-5">
          <div className="mb-3 flex items-center justify-between gap-2">
            <Kicker>Materials slipping ({Object.keys(delays).length})</Kicker>
            <div className="flex items-center gap-2">
              {Object.keys(delays).length > 0 && (
                <button onClick={() => setDelays({})}
                  className="text-xs text-faint transition hover:text-red">clear all</button>
              )}
              {suppliers.length > 0 && (
                <select className={cn(input, "!py-1.5 text-xs")} value=""
                  onChange={(e) => e.target.value && addSupplier(e.target.value)} title="Slip every material from one supplier">
                  <option value="">+ slip a supplier's order</option>
                  {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              )}
              {addable.length > 0 && (
                <select className={cn(input, "!py-1.5 text-xs")} value=""
                  onChange={(e) => e.target.value && toggle(e.target.value)}>
                  <option value="">+ add material</option>
                  {addable.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
              )}
            </div>
          </div>
          {Object.keys(delays).length === 0 ? (
            <div className="text-sm text-muted">No materials selected. Add one, or click a material in the graph.</div>
          ) : (
            <div className="flex flex-col gap-3">
              {Object.entries(delays).map(([id, days]) => (
                <div key={id} className="rounded-lg border border-amber/20 bg-amber/[0.04] p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm text-text">{name(id)}</span>
                    <button onClick={() => toggle(id)} className="text-faint hover:text-red"><X size={15} /></button>
                  </div>
                  <div className="flex items-center gap-3">
                    <input type="range" min={1} max={30} value={days} onChange={(e) => setDelay(id, +e.target.value)}
                      className="flex-1" style={{ accentColor: "var(--amber)" }} />
                    <span className="w-10 text-right font-mono text-sm text-amber">{days}d</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
        </TourTarget>

        {report && (
          <TourTarget name="cascade-verdict">
          <GlassCard className={cn("flex items-center gap-4 self-start p-5", breaks ? "border-red/40" : "border-green/30")}>
            <div className={breaks ? "text-red" : "text-green"}>
              {breaks ? <AlertTriangle size={28} /> : <ShieldCheck size={28} />}
            </div>
            <div>
              <div className="font-display text-xl font-bold">
                {breaks
                  ? <>Handover breaks — <span className="text-red">+{report.handover_slip_days} days</span></>
                  : <>Handover holds — <span className="text-green">float absorbs it</span></>}
              </div>
              <div className="mt-0.5 text-sm text-muted">
                with {Object.keys(debouncedDelays).length} material
                {Object.keys(debouncedDelays).length !== 1 && "s"} running late
                {" · "}handover {report.baseline_handover}
                {breaks && <> → <span className="text-text">{report.handover_date}</span></>}
                {" · "}we're <b className="text-text">{sureness(report.confidence)}</b> of the dates
              </div>
            </div>
          </GlassCard>
          </TourTarget>
        )}
      </div>

      {/* THE GRAPH — click materials to toggle them into the delay set */}
      <TourTarget name="cascade-graph">
      {project
        ? <GraphCanvas project={project} delayedIds={delayedIds} slippedIds={slippedIds}
            handoverBreaks={breaks} onToggleMaterial={toggle} />
        : <div className="flex h-[68vh] min-h-[560px] items-center justify-center rounded-2xl border border-line bg-black/40 text-sm text-muted">
            <span className="animate-pulse">loading the supply graph…</span>
          </div>}
      </TourTarget>

      {/* details */}
      {report && (
        <TourTarget name="cascade-details" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <GlassCard className="p-5">
            <Kicker className="mb-3">Jobs pushed back · {report.slipped.length}</Kicker>
            {report.slipped.length === 0
              ? <div className="text-sm text-muted">None — there's enough spare time in the schedule to absorb this.</div>
              : <div className="flex flex-col gap-2">
                  {report.slipped.slice(0, 6).map((s) => (
                    <div key={s.activity} className="flex items-center justify-between gap-3 text-sm">
                      <span className="min-w-0 truncate text-muted">{s.name}</span>
                      <span className="shrink-0 font-mono text-xs text-red">
                        {s.slip_days} day{s.slip_days !== 1 && "s"} later
                      </span>
                    </div>
                  ))}
                  {report.slipped.length > 6 && <div className="text-xs text-faint">+{report.slipped.length - 6} more</div>}
                </div>}
            {report.absorbed.length > 0 && (
              <div className="mt-3 border-t border-line pt-3 text-xs text-muted">
                <span className="text-green">{report.absorbed.length}</span> more had spare time and weren't affected
              </div>
            )}
          </GlassCard>

          <GlassCard className={cn("p-5", breaks && "border-amber/20")}>
            <div className="mb-3 flex items-center gap-2"><Truck size={15} className={breaks ? "text-amber" : "text-faint"} />
              <span className="kicker">Alternate supply</span></div>
            {!breaks
              ? <div className="text-sm text-muted">Not needed — handover is safe.</div>
              : (() => {
                  const rows = Object.entries(alts).flatMap(([id, a]) =>
                    (a.alternates?.filter((x) => x.meets_roj) ?? []).slice(0, 1).map((x) => ({ id, x })));
                  return rows.length === 0
                    ? <div className="text-sm text-muted">No fast switch — expedite the current orders.</div>
                    : <div className="flex flex-col gap-2">
                        {rows.map(({ id, x }) => (
                          <div key={id} className="flex items-center justify-between gap-3 text-sm">
                            <span className="min-w-0 truncate text-text">{x.name}
                              <span className="text-faint text-xs"> for {name(id)}</span></span>
                            <Badge tone="green">can still make it</Badge>
                          </div>
                        ))}
                      </div>;
                })()}
          </GlassCard>
        </TourTarget>
      )}

      {/* what it costs, and the cheapest ways out — the answer to "so what?" */}
      <RecoveryPlan delays={debouncedDelays} />

      {/* and what it costs to sit on it. Anchored to the worst single delay,
          because the decay story is about one order's window closing. */}
      {breaks && worstDelay && (
        <CostOfWaiting materialId={worstDelay[0]} delayDays={worstDelay[1]} />
      )}

      {/* the last mile: the messages this analysis is useless without */}
      <TellSomeone delays={debouncedDelays} />
    </div>
  );
}
