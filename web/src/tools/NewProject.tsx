import { useState } from "react";
import { Plus, Trash2, Rocket, Loader2, Building2, Package, CalendarClock, Flag } from "lucide-react";
import { api } from "../lib/api";
import { GlassCard, Button, Kicker } from "../components/primitives";
import { cn } from "../lib/cn";

const uid = () => crypto.randomUUID();
const REGIONS = ["north", "south", "east", "west", "central"];
const todayISO = new Date().toISOString().slice(0, 10);
const input = "w-full rounded-lg border border-line bg-black/30 px-3 py-2 text-sm outline-none focus:border-amber/50";

interface Sup { key: string; name: string; region: string; reliability: string }
interface Mat { key: string; name: string; supplierKey: string; arrival: string; roj: string; confidence: number }
interface Act { key: string; name: string; duration: string; needs: string[]; deps: string[] }

export default function NewProject() {
  const [name, setName] = useState("");
  const [start, setStart] = useState(todayISO);
  const [suppliers, setSuppliers] = useState<Sup[]>([{ key: uid(), name: "", region: "west", reliability: "" }]);
  const [materials, setMaterials] = useState<Mat[]>([{ key: uid(), name: "", supplierKey: "", arrival: "", roj: "", confidence: 0.8 }]);
  const [activities, setActivities] = useState<Act[]>([{ key: uid(), name: "", duration: "5", needs: [], deps: [] }]);
  const [handoverKey, setHandoverKey] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const setSup = (k: string, p: Partial<Sup>) => setSuppliers((x) => x.map((s) => s.key === k ? { ...s, ...p } : s));
  const setMat = (k: string, p: Partial<Mat>) => setMaterials((x) => x.map((m) => m.key === k ? { ...m, ...p } : m));
  const setAct = (k: string, p: Partial<Act>) => setActivities((x) => x.map((a) => a.key === k ? { ...a, ...p } : a));
  const toggle = (arr: string[], v: string) => arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];

  async function create() {
    setErr("");
    const sups = suppliers.filter((s) => s.name.trim());
    const mats = materials.filter((m) => m.name.trim());
    const acts = activities.filter((a) => a.name.trim());
    if (!name.trim()) return setErr("Give the project a name.");
    if (!sups.length) return setErr("Add at least one supplier.");
    if (!mats.some((m) => m.supplierKey && m.arrival && m.roj)) return setErr("Add a material with a supplier, expected arrival and required-on-job date.");
    if (!acts.length) return setErr("Add at least one schedule activity.");

    const supId = new Map(sups.map((s, i) => [s.key, `SUP-${i + 1}`]));
    const matId = new Map(mats.map((m, i) => [m.key, `MAT-${i + 1}`]));
    const actId = new Map(acts.map((a, i) => [a.key, `ACT-${i + 1}`]));

    const payload = {
      project: { name: name.trim(), start_date: start,
        handover_milestone: handoverKey && actId.get(handoverKey) ? actId.get(handoverKey)! : undefined },
      suppliers: sups.map((s, i) => ({ id: `SUP-${i + 1}`, name: s.name.trim(),
        region: s.region || undefined, reliability: s.reliability ? +s.reliability : undefined })),
      materials: mats.filter((m) => m.supplierKey).map((m, i) => ({ id: `MAT-${i + 1}`, name: m.name.trim(),
        supplier: supId.get(m.supplierKey)!, expected_arrival: m.arrival, roj_date: m.roj, confidence: m.confidence })),
      activities: acts.map((a, i) => ({ id: `ACT-${i + 1}`, name: a.name.trim(), duration_days: +a.duration || 1,
        needs_materials: a.needs.map((k) => matId.get(k)!).filter(Boolean), depends_on: a.deps.map((k) => actId.get(k)!).filter(Boolean) })),
    };
    setBusy(true);
    try {
      await api.createProject(payload);
      window.location.assign("/dashboard/cascade");
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e));
      setBusy(false);
    }
  }

  const matsForPicker = materials.filter((m) => m.name.trim());

  return (
    <div className="mx-auto max-w-[860px] pb-16">
      <p className="mb-6 max-w-2xl text-sm leading-relaxed text-muted">
        Build a project by entering its suppliers, materials and schedule — no files, no code.
        Foreman fills in the rest and you can simulate delays immediately.
      </p>

      <Section icon={<CalendarClock size={15} />} title="Project">
        <div className="grid gap-3 sm:grid-cols-[1fr_180px]">
          <label><div className="kicker mb-1.5">Project name</div>
            <input className={input} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Riverside Hospital — Phase 1" /></label>
          <label><div className="kicker mb-1.5">Start date</div>
            <input type="date" className={input} value={start} onChange={(e) => setStart(e.target.value)} /></label>
        </div>
      </Section>

      <Section icon={<Building2 size={15} />} title="Suppliers"
        action={<AddBtn onClick={() => setSuppliers((x) => [...x, { key: uid(), name: "", region: "west", reliability: "" }])} />}>
        <div className="flex flex-col gap-2">
          {suppliers.map((s) => (
            <div key={s.key} className="grid items-center gap-2 sm:grid-cols-[1fr_120px_110px_32px]">
              <input className={input} placeholder="Supplier name" value={s.name} onChange={(e) => setSup(s.key, { name: e.target.value })} />
              <select className={input} value={s.region} onChange={(e) => setSup(s.key, { region: e.target.value })}>
                {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <input className={input} type="number" min={0} max={1} step={0.05} placeholder="reliability" value={s.reliability} onChange={(e) => setSup(s.key, { reliability: e.target.value })} />
              <RemoveBtn onClick={() => setSuppliers((x) => x.filter((y) => y.key !== s.key))} />
            </div>
          ))}
        </div>
      </Section>

      <Section icon={<Package size={15} />} title="Materials"
        action={<AddBtn onClick={() => setMaterials((x) => [...x, { key: uid(), name: "", supplierKey: "", arrival: "", roj: "", confidence: 0.8 }])} />}>
        <div className="flex flex-col gap-3">
          {materials.map((m) => (
            <div key={m.key} className="rounded-lg border border-line bg-black/20 p-3">
              <div className="grid items-center gap-2 sm:grid-cols-[1fr_1fr_32px]">
                <input className={input} placeholder="Material name (e.g. structural steel)" value={m.name} onChange={(e) => setMat(m.key, { name: e.target.value })} />
                <select className={input} value={m.supplierKey} onChange={(e) => setMat(m.key, { supplierKey: e.target.value })}>
                  <option value="">— supplier —</option>
                  {suppliers.filter((s) => s.name.trim()).map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
                </select>
                <RemoveBtn onClick={() => setMaterials((x) => x.filter((y) => y.key !== m.key))} />
              </div>
              <div className="mt-2 grid gap-2 sm:grid-cols-3">
                <label><div className="kicker mb-1">Expected arrival</div><input type="date" className={input} value={m.arrival} onChange={(e) => setMat(m.key, { arrival: e.target.value })} /></label>
                <label><div className="kicker mb-1">Required on job</div><input type="date" className={input} value={m.roj} onChange={(e) => setMat(m.key, { roj: e.target.value })} /></label>
                <label><div className="kicker mb-1">Confidence <span className="text-amber">{Math.round(m.confidence * 100)}%</span></div>
                  <input type="range" min={0.3} max={1} step={0.01} value={m.confidence} onChange={(e) => setMat(m.key, { confidence: +e.target.value })} className="w-full" style={{ accentColor: "var(--amber)" }} /></label>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section icon={<Flag size={15} />} title="Schedule activities"
        action={<AddBtn onClick={() => setActivities((x) => [...x, { key: uid(), name: "", duration: "5", needs: [], deps: [] }])} />}>
        <div className="mb-2 text-xs text-faint">Pick which materials each activity needs, and which activities must finish first. Mark the final one as the handover.</div>
        <div className="flex flex-col gap-3">
          {activities.map((a, idx) => (
            <div key={a.key} className="rounded-lg border border-line bg-black/20 p-3">
              <div className="grid items-center gap-2 sm:grid-cols-[1fr_110px_auto_32px]">
                <input className={input} placeholder={`Activity ${idx + 1} name`} value={a.name} onChange={(e) => setAct(a.key, { name: e.target.value })} />
                <input className={input} type="number" min={1} placeholder="days" value={a.duration} onChange={(e) => setAct(a.key, { duration: e.target.value })} />
                <button onClick={() => setHandoverKey(handoverKey === a.key ? null : a.key)}
                  className={cn("rounded-lg border px-3 py-2 text-xs transition", handoverKey === a.key ? "border-amber bg-amber/15 text-amber" : "border-line text-muted hover:text-text")}>
                  <Flag size={12} className="mr-1 inline" />handover
                </button>
                <RemoveBtn onClick={() => setActivities((x) => x.filter((y) => y.key !== a.key))} />
              </div>
              {matsForPicker.length > 0 && (
                <div className="mt-2.5">
                  <div className="kicker mb-1.5">needs materials</div>
                  <div className="flex flex-wrap gap-1.5">
                    {matsForPicker.map((m) => (
                      <Chip key={m.key} active={a.needs.includes(m.key)} onClick={() => setAct(a.key, { needs: toggle(a.needs, m.key) })}>{m.name}</Chip>
                    ))}
                  </div>
                </div>
              )}
              {activities.filter((o) => o.key !== a.key && o.name.trim()).length > 0 && (
                <div className="mt-2.5">
                  <div className="kicker mb-1.5">depends on (must finish first)</div>
                  <div className="flex flex-wrap gap-1.5">
                    {activities.filter((o) => o.key !== a.key && o.name.trim()).map((o) => (
                      <Chip key={o.key} tone="steel" active={a.deps.includes(o.key)} onClick={() => setAct(a.key, { deps: toggle(a.deps, o.key) })}>{o.name}</Chip>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </Section>

      {err && <div className="mb-4 rounded-lg border border-red/40 bg-red/10 px-4 py-3 text-sm text-red">{err}</div>}
      <Button onClick={create} className="!px-6 !py-3">
        {busy ? <><Loader2 size={16} className="animate-spin" /> creating…</> : <><Rocket size={16} /> Create & launch project</>}
      </Button>
    </div>
  );
}

function Section({ icon, title, action, children }: { icon: React.ReactNode; title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <GlassCard className="mb-4 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2"><span className="text-amber">{icon}</span><Kicker>{title}</Kicker></div>
        {action}
      </div>
      {children}
    </GlassCard>
  );
}
const AddBtn = ({ onClick }: { onClick: () => void }) => (
  <button onClick={onClick} className="flex items-center gap-1 rounded-md border border-line px-2.5 py-1 text-xs text-muted transition hover:border-amber/40 hover:text-amber"><Plus size={13} /> add</button>
);
const RemoveBtn = ({ onClick }: { onClick: () => void }) => (
  <button onClick={onClick} className="flex h-8 w-8 items-center justify-center rounded-lg text-faint transition hover:text-red"><Trash2 size={14} /></button>
);
function Chip({ active, onClick, children, tone = "amber" }: { active: boolean; onClick: () => void; children: React.ReactNode; tone?: "amber" | "steel" }) {
  return (
    <button onClick={onClick} className={cn("rounded-full border px-2.5 py-1 text-xs transition",
      active ? (tone === "amber" ? "border-amber bg-amber/15 text-amber" : "border-steel-bright bg-white/10 text-steel-bright") : "border-line text-muted hover:text-text")}>
      {children}
    </button>
  );
}
