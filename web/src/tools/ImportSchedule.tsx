import { useState } from "react";
import { Loader2, Check, AlertTriangle, Rocket, ChevronDown, SearchCheck } from "lucide-react";
import { api, type ImportReport } from "../lib/api";
import { GlassCard, Kicker, Badge } from "../components/primitives";
import FilePick from "../components/FilePick";
import { cn } from "../lib/cn";

/* Bring in a real schedule. On a job site the P6 file is the ground truth, so
 * this is the path in for anyone with a project already running: drop in the
 * .xer (or an activity export) and, if there is one, the P&D log. Nothing is
 * saved until the user has seen what Foreman understood -- where each part
 * came from, what it had to approximate, and whether its starting schedule
 * reproduces P6's. */

const SCHEDULE_TYPES = ".xer,.csv,.tsv,.txt,.xlsx,.xlsm";
const PD_TYPES = ".csv,.tsv,.xlsx,.xlsm";
const msg = (e: unknown) => String(e instanceof Error ? e.message : e);

export default function ImportSchedule() {
  const [schedule, setSchedule] = useState<File | null>(null);
  const [pd, setPd] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [project, setProject] = useState("");
  const [name, setName] = useState("");
  const [nameEdited, setNameEdited] = useState(false);
  const [busy, setBusy] = useState<"checking" | "saving" | null>(null);
  const [error, setError] = useState("");
  const [showNotes, setShowNotes] = useState(false);

  function pick(set: (f: File | null) => void) {
    return (f: File | null) => { set(f); setReport(null); setError(""); };
  }

  async function check(forProject?: string) {
    if (!schedule) return;
    setBusy("checking"); setError("");
    try {
      const r = await api.importSchedule({ schedule, pd, project: forProject });
      setReport(r);
      setProject(r.chosen);
      if (!nameEdited) setName(r.suggested_name);
    } catch (e) { setError(msg(e)); setReport(null); }
    finally { setBusy(null); }
  }

  async function save() {
    if (!schedule || !report) return;
    setBusy("saving"); setError("");
    try {
      await api.importSchedule({ schedule, pd, project, name: name.trim(), commit: true });
      window.location.assign("/dashboard/today");
    } catch (e) { setError(msg(e)); setBusy(null); }
  }

  return (
    <div className="flex flex-col gap-5">
      <GlassCard className="p-6">
        <Kicker>Step 1</Kicker>
        <h2 className="mt-1.5 font-display text-2xl font-bold">Import a P6 schedule</h2>
        <p className="mt-1.5 text-sm text-muted">
          The <b className="text-text">.xer</b> export is best: it carries the real links between activities.
          An activity table (CSV or Excel) works too. Add the P&amp;D log if you have one, so Foreman
          tracks your real items and their status.
        </p>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <FilePick label="Schedule" hint=".xer, or an activity table (CSV / Excel)"
            accept={SCHEDULE_TYPES} file={schedule} onFile={pick(setSchedule)} />
          <FilePick label="P&D log" optional hint="CSV or Excel, one row per item"
            accept={PD_TYPES} file={pd} onFile={pick(setPd)} />
        </div>

        <button onClick={() => check()} disabled={!schedule || busy !== null}
          className="mt-4 inline-flex items-center gap-2 rounded-lg bg-amber px-5 py-2.5 text-sm font-medium
            text-black transition hover:bg-amber-bright disabled:cursor-not-allowed disabled:opacity-40">
          {busy === "checking" ? <Loader2 size={15} className="animate-spin" /> : <SearchCheck size={15} />}
          {busy === "checking" ? "reading the schedule…" : "Check the files"}
        </button>
        <span className="ml-3 text-xs text-faint">Nothing is saved until you confirm.</span>
      </GlassCard>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red/40 bg-red/10 px-4 py-3 text-sm text-red">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />{error}
        </div>
      )}

      {report && (
        <GlassCard className="p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <Kicker>Step 2 · what Foreman understood</Kicker>
              <div className="mt-1.5 text-sm text-muted">
                {report.source}{report.pd_source && <> + {report.pd_source}</>}
              </div>
            </div>
            <Badge tone="steel">{report.format_label}</Badge>
          </div>

          {report.projects.length > 1 && (
            <label className="mt-4 block">
              <div className="kicker mb-1.5">This file holds {report.projects.length} projects — which one?</div>
              <select value={project} disabled={busy !== null}
                onChange={(e) => { setProject(e.target.value); check(e.target.value); }}
                className="w-full rounded-lg border border-line bg-black/30 px-3 py-2 text-sm outline-none focus:border-amber/50">
                {report.projects.map((p) => (
                  <option key={p.id} value={p.id}>{p.name} · {p.activities.toLocaleString()} activities</option>
                ))}
              </select>
            </label>
          )}

          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Fact value={report.counts.activities.toLocaleString()} label="activities" />
            <Fact value={report.counts.links.toLocaleString()} label="links" sub={report.links_source} />
            <Fact value={report.counts.materials.toLocaleString()} label="items tracked" sub={report.materials_source} />
            <Fact value={report.handover.p6_finish ?? "—"} label="handover (P6)" sub={report.handover.name} />
          </div>

          <div className={cn("mt-4 flex items-start gap-2 rounded-lg border px-4 py-3 text-sm",
            report.handover.matches_p6 ? "border-green/30 bg-green/[0.06] text-green" : "border-red/40 bg-red/10 text-red")}>
            {report.handover.matches_p6 ? <Check size={15} className="mt-0.5 shrink-0" /> : <AlertTriangle size={15} className="mt-0.5 shrink-0" />}
            {report.handover.matches_p6
              ? "Foreman's starting schedule matches P6: every activity starts on its P6 date before anything is delayed."
              : `${report.handover.moved_before_any_delay} activities start later in Foreman than in P6 before any delay — the conversion missed something.`}
          </div>

          {report.warnings.length > 0 && (
            <div className="mt-4 flex flex-col gap-2">
              {report.warnings.map((w) => (
                <div key={w} className="flex items-start gap-2 rounded-lg border border-amber/25 bg-amber/[0.06] px-4 py-2.5 text-[0.82rem] text-text">
                  <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber" />{w}
                </div>
              ))}
            </div>
          )}

          <button onClick={() => setShowNotes((s) => !s)} className="mt-4 flex items-center gap-1.5 text-xs text-faint transition hover:text-amber">
            <ChevronDown size={13} className={cn("transition", showNotes && "rotate-180")} />
            how it was converted
          </button>
          {showNotes && (
            <ul className="mt-2 flex flex-col gap-1 text-[0.8rem] leading-relaxed text-muted">
              {report.notes.map((n) => <li key={n}>· {n}</li>)}
              <li className="text-faint">· confidence: {report.confidence_source}</li>
            </ul>
          )}

          <div className="mt-6 grid items-end gap-3 sm:grid-cols-[1fr_auto]">
            <label>
              <div className="kicker mb-1.5">Name in Foreman</div>
              <input value={name} onChange={(e) => { setName(e.target.value); setNameEdited(true); }}
                className="w-full rounded-lg border border-line bg-black/30 px-3 py-2 text-sm outline-none focus:border-amber/50" />
            </label>
            <button onClick={save} disabled={busy !== null || !name.trim()}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-amber px-5 py-2.5 text-sm font-medium
                text-black transition hover:bg-amber-bright disabled:cursor-not-allowed disabled:opacity-40">
              {busy === "saving" ? <Loader2 size={15} className="animate-spin" /> : <Rocket size={15} />}
              {busy === "saving" ? "importing…" : "Import & open"}
            </button>
          </div>
        </GlassCard>
      )}
    </div>
  );
}

function Fact({ value, label, sub }: { value: string; label: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-line bg-black/20 px-4 py-3">
      <div className="font-display text-xl font-bold leading-tight">{value}</div>
      <div className="kicker mt-1">{label}</div>
      {sub && <div className="mt-1 text-[0.72rem] leading-snug text-faint">{sub}</div>}
    </div>
  );
}

