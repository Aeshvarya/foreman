import { useState } from "react";
import { Loader2, AlertTriangle, GitCompare, ArrowRight } from "lucide-react";
import { api, type ChangeRow, type Comparison, type SnapshotOption } from "../lib/api";
import { GlassCard, Kicker } from "../components/primitives";
import FilePick from "../components/FilePick";
import { cn } from "../lib/cn";

/* The weekly question, for the whole project at once: between this update and
 * the last one, what moved, what quietly lost float, and did completion slip?
 * Read straight from P6's own dates and float — nothing modelled — and nothing
 * saved: comparing two files never touches the projects. */

const TYPES = ".xer,.csv,.tsv,.txt,.xlsx,.xlsm";
const msg = (e: unknown) => String(e instanceof Error ? e.message : e);
const signed = (n: number) => (n > 0 ? `+${n}` : `${n}`);
const days = (v: number | null) => (v === null ? "—" : `${Math.round(v)}d`);

export default function Compare() {
  const [older, setOlder] = useState<File | null>(null);
  const [newer, setNewer] = useState<File | null>(null);
  const [res, setRes] = useState<Comparison | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(keys?: { older_key?: string; newer_key?: string }) {
    if (!older) return;
    setBusy(true); setError("");
    try { setRes(await api.compare({ older, newer, ...keys })); }
    catch (e) { setError(msg(e)); setRes(null); }
    finally { setBusy(false); }
  }
  const pick = (set: (f: File | null) => void) => (f: File | null) => { set(f); setRes(null); setError(""); };
  const shift = res?.completion.shift_days ?? null;

  return (
    <div className="mx-auto flex max-w-[1000px] flex-col gap-5">
      <GlassCard className="p-6">
        <h2 className="font-display text-2xl font-bold">Compare two schedule updates</h2>
        <p className="mt-1.5 text-sm text-muted">
          Drop in last update's and this update's P6 export (.xer or activity table). If both versions
          are in one file, one file is enough. Nothing is saved.
        </p>
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <FilePick label="Older update" hint=".xer or activity table" accept={TYPES} file={older} onFile={pick(setOlder)} />
          <FilePick label="Newer update" optional hint="leave empty if both are in the first file"
            accept={TYPES} file={newer} onFile={pick(setNewer)} />
        </div>
        <button onClick={() => run()} disabled={!older || busy}
          className="mt-4 inline-flex items-center gap-2 rounded-lg bg-amber px-5 py-2.5 text-sm font-medium
            text-black transition hover:bg-amber-bright disabled:cursor-not-allowed disabled:opacity-40">
          {busy ? <Loader2 size={15} className="animate-spin" /> : <GitCompare size={15} />}
          {busy ? "comparing…" : "Compare"}
        </button>
      </GlassCard>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red/40 bg-red/10 px-4 py-3 text-sm text-red">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />{error}
        </div>
      )}

      {res && (
        <>
          <GlassCard className="p-6">
            <Kicker>What changed</Kicker>
            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-muted">
              {res.older.label} <ArrowRight size={14} className="text-faint" /> <span className="text-text">{res.newer.label}</span>
            </div>
            {(res.older_options.length > 1 || res.newer_options.length > 1) && (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <VersionSelect label="Older" options={res.older_options} value={res.older_key} disabled={busy}
                  onChange={(k) => run({ older_key: k, newer_key: res.newer_key })} />
                <VersionSelect label="Newer" options={res.newer_options} value={res.newer_key} disabled={busy}
                  onChange={(k) => run({ older_key: res.older_key, newer_key: k })} />
              </div>
            )}
            <p className="mt-5 font-display text-lg leading-snug">{res.headline}</p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <Tile value={shift === null ? "—" : shift === 0 ? "held" : `${signed(shift)}d`} label="completion"
                tone={shift === null || shift === 0 ? "steel" : shift > 0 ? "red" : "green"}
                sub={res.completion.newer ? `${res.completion.newer.name} · ${res.completion.newer.finish}` : undefined} />
              <Tile value={res.counts.matched.toLocaleString()} label="activities matched"
                sub={`${res.counts.added} new · ${res.counts.removed} removed`} />
              <Tile value={res.counts.later.toLocaleString()} label="finish later" tone={res.counts.later ? "red" : "steel"}
                sub={res.median_shift_days !== null ? `median +${res.median_shift_days}d` : undefined} />
              <Tile value={res.counts.earlier.toLocaleString()} label="finish earlier" tone={res.counts.earlier ? "green" : "steel"} />
              <Tile value={res.counts.lost_float.toLocaleString()} label="lost float" tone={res.counts.lost_float ? "amber" : "steel"}
                sub={`${res.counts.gained_float.toLocaleString()} gained`} />
              <Tile value={res.counts.newly_critical.toLocaleString()} label="became critical" tone={res.counts.newly_critical ? "red" : "steel"} />
            </div>
          </GlassCard>
          {res.deliveries.length > 0 && <Changes title="Deliveries that moved or lost float" rows={res.deliveries} />}
          {res.top_slipped.length > 0 && <Changes title="Slipped the most (still to finish)" rows={res.top_slipped} />}
          {res.top_float_lost.length > 0 && <Changes title="Lost the most float (still to finish)" rows={res.top_float_lost} />}
        </>
      )}
    </div>
  );
}

function VersionSelect({ label, options, value, onChange, disabled }: {
  label: string; options: SnapshotOption[]; value: string; onChange: (k: string) => void; disabled: boolean;
}) {
  return (
    <label>
      <div className="kicker mb-1.5">{label} version</div>
      <select value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-line bg-black/30 px-3 py-2 text-sm outline-none focus:border-amber/50">
        {options.map((o) => (
          <option key={o.key} value={o.key}>
            {o.label} · {o.activities.toLocaleString()} activities{o.current ? "" : " · earlier upload"}
          </option>
        ))}
      </select>
    </label>
  );
}

const TONE = { red: "text-red", green: "text-green", amber: "text-amber", steel: "text-text" };

function Tile({ value, label, sub, tone = "steel" }: { value: string; label: string; sub?: string; tone?: keyof typeof TONE }) {
  return (
    <div className="rounded-xl border border-line bg-black/20 px-4 py-3">
      <div className={cn("font-display text-xl font-bold leading-tight", TONE[tone])}>{value}</div>
      <div className="kicker mt-1">{label}</div>
      {sub && <div className="mt-1 text-[0.72rem] leading-snug text-faint">{sub}</div>}
    </div>
  );
}

function Changes({ title, rows }: { title: string; rows: ChangeRow[] }) {
  return (
    <GlassCard className="p-5">
      <Kicker className="mb-3">{title}</Kicker>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[0.72rem] uppercase tracking-wider text-faint">
              <th className="py-1.5 pr-3 font-normal">Activity</th>
              <th className="py-1.5 pr-3 font-normal">Finish</th>
              <th className="py-1.5 text-right font-normal">Moved</th>
              <th className="py-1.5 pl-3 text-right font-normal">Float</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-line align-top">
                <td className="py-2 pr-3">
                  <div className="text-text">{r.name}</div>
                  <div className="font-mono text-[0.7rem] text-faint">{r.id}</div>
                </td>
                <td className="whitespace-nowrap py-2 pr-3 text-muted">
                  {r.old_finish} → <span className="text-text">{r.new_finish}</span>
                </td>
                <td className={cn("whitespace-nowrap py-2 text-right font-mono",
                  r.shift_days > 0 ? "text-red" : r.shift_days < 0 ? "text-green" : "text-faint")}>
                  {signed(r.shift_days)}d
                </td>
                <td className="whitespace-nowrap py-2 pl-3 text-right font-mono text-muted">
                  {days(r.old_float)} → <span className={cn(
                    r.new_float !== null && r.old_float !== null && r.new_float < r.old_float ? "text-amber" : "text-text")}>
                    {days(r.new_float)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
}
