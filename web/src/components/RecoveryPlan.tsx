import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  IndianRupee, TrendingDown, Truck, Repeat, MoonStar, ChevronDown,
  Sparkles, SlidersHorizontal, Info, Check,
} from "lucide-react";
import { api, type RecoveryPlan as Plan, type RecoveryOption, type MoneySettings } from "../lib/api";
import { GlassCard, Kicker, Badge } from "./primitives";
import { cn } from "../lib/cn";

/* What a delay costs, and the cheapest ways out of it.
 *
 * Deliberately written for someone who has never opened a Gantt chart: the
 * headline is a rupee number, the options are sentences ("Pay to speed up the
 * structural steel"), and the maths is one click away rather than on the face
 * of the card. Everything the engine returns already carries its own formula
 * and source, so nothing here invents a number — it only arranges them. */

const KIND_ICON = {
  expedite: Truck,
  switch: Repeat,
  overtime: MoonStar,
  none: TrendingDown,
} as const;

export default function RecoveryPlan({ delays }: { delays: Record<string, number> }) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => {
    const ids = Object.keys(delays);
    if (ids.length === 0) { setPlan(null); return; }
    let live = true;
    setLoading(true);
    api.recovery(delays)
      .then((p) => { if (live) { setPlan(p); setOpenId(p.best?.id ?? null); } })
      .catch(() => { if (live) setPlan(null); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [JSON.stringify(delays)]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!plan && !loading) return null;

  const safe = plan && plan.handover_slip_days === 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <Kicker>What this costs you</Kicker>
          <h2 className="font-display text-lg font-bold">
            {safe ? "Nothing — the date still holds" : "And the cheapest ways out of it"}
          </h2>
        </div>
        <button onClick={() => setShowSettings((s) => !s)}
          className="flex shrink-0 items-center gap-1.5 text-xs text-faint transition hover:text-amber">
          <SlidersHorizontal size={13} /> Edit these numbers
        </button>
      </div>

      <AnimatePresence>
        {showSettings && <MoneySettingsPanel onClose={() => setShowSettings(false)}
          onSaved={() => api.recovery(delays).then(setPlan).catch(() => {})} />}
      </AnimatePresence>

      {loading && !plan && (
        <GlassCard className="p-5 text-sm text-muted">
          <span className="animate-pulse">working out what this costs…</span>
        </GlassCard>
      )}

      {plan && !safe && (
        <>
          {/* the headline rupee number */}
          <GlassCard className="border-red/30 p-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-red">
                  <IndianRupee size={18} />
                  <span className="kicker !text-red/80">If nobody does anything</span>
                </div>
                <div className="mt-1 font-display text-3xl font-bold text-red">
                  {plan.exposure.total_label}
                </div>
                <div className="mt-1 text-sm text-muted">
                  {plan.handover_slip_days} day{plan.handover_slip_days !== 1 && "s"} late,
                  at {plan.exposure.per_day_label} a day
                </div>
              </div>
              <div className="flex flex-col gap-2">
                {plan.exposure.lines.map((l) => (
                  <div key={l.key} className="flex items-center gap-3 text-sm">
                    <span className="text-muted">{l.label}</span>
                    <span className="font-mono text-text">{l.formula}</span>
                    {l.source === "assumed" && (
                      <span title={l.basis} className="cursor-help text-faint hover:text-amber">
                        <Info size={13} />
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
            {plan.exposure.assumed && (
              <p className="mt-3 border-t border-line pt-3 text-xs text-faint">
                Some of these are our starting assumptions, not your contract. Hover the ⓘ to see
                where each came from, or edit them above.
              </p>
            )}
          </GlassCard>

          {/* the fixes, best first */}
          <div className="flex flex-col gap-2.5">
            {plan.options.map((o, i) => (
              <OptionCard key={o.id} option={o} best={i === 0}
                open={openId === o.id} onToggle={() => setOpenId(openId === o.id ? null : o.id)} />
            ))}
            {plan.options.length === 0 && (
              <GlassCard className="p-5 text-sm text-muted">
                No fix buys back a day here — the delay is already past the point where money helps.
                Tell the client early; that is the only move left.
              </GlassCard>
            )}
          </div>
        </>
      )}

      {plan && safe && (
        <GlassCard className="border-green/30 p-5 text-sm text-muted">
          This delay is absorbed by spare time in the schedule. Nothing to spend, nothing to chase —
          just keep an eye on it.
        </GlassCard>
      )}
    </div>
  );
}

function OptionCard({ option: o, best, open, onToggle }: {
  option: RecoveryOption; best: boolean; open: boolean; onToggle: () => void;
}) {
  const Icon = KIND_ICON[o.kind] ?? Truck;
  const worthIt = o.net > 0;

  return (
    <GlassCard className={cn("overflow-hidden", best && worthIt && "border-amber/40")}>
      <button onClick={onToggle} className="flex w-full items-center gap-4 p-4 text-left">
        <div className={cn("grid h-10 w-10 shrink-0 place-items-center rounded-xl",
          best && worthIt ? "bg-amber/15 text-amber" : "bg-white/5 text-muted")}>
          <Icon size={18} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{o.title}</span>
            {best && worthIt && <Badge tone="amber"><Sparkles size={10} className="mr-1" /> best value</Badge>}
            {!worthIt && <Badge tone="red">costs more than it saves</Badge>}
          </div>
          <p className="mt-0.5 truncate text-sm text-muted">{o.plain}</p>
        </div>

        <div className="hidden shrink-0 text-right sm:block">
          <div className="font-mono text-sm text-text">
            buys {o.days_saved} day{o.days_saved !== 1 && "s"}
          </div>
          <div className="text-xs text-faint">costs {o.cost_label}</div>
        </div>

        <div className="shrink-0 text-right">
          <div className={cn("font-display text-lg font-bold", worthIt ? "text-green" : "text-red")}>
            {worthIt ? `keeps ${o.net_label}` : o.net_label}
          </div>
        </div>

        <ChevronDown size={16} className={cn("shrink-0 text-faint transition-transform", open && "rotate-180")} />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}>
            <div className="grid gap-5 border-t border-line px-4 py-4 sm:grid-cols-2">
              <div>
                <Kicker className="mb-2">How to do it</Kicker>
                <ol className="flex flex-col gap-2">
                  {o.how.map((step, i) => (
                    <li key={i} className="flex gap-2.5 text-sm text-muted">
                      <span className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full
                        bg-white/5 font-mono text-[0.6rem] text-faint">{i + 1}</span>
                      {step}
                    </li>
                  ))}
                </ol>
              </div>
              <div>
                <Kicker className="mb-2">Why we say that</Kicker>
                <p className="text-sm leading-relaxed text-muted">{o.why}</p>
                <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 border-t border-line pt-3 font-mono text-xs text-faint">
                  <span>days bought <b className="text-text">{o.days_saved}</b></span>
                  <span>you spend <b className="text-text">{o.cost_label}</b></span>
                  <span>penalty avoided <b className="text-text">
                    {o.avoided !== undefined ? fmtShort(o.avoided) : "—"}</b></span>
                  <span>how sure <b className="text-text">{o.confidence}</b></span>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </GlassCard>
  );
}

/* The assumptions drawer. A judge asking "where did ₹2.5 lakh come from?"
   should get an answer from the product, not from the presenter. */
function MoneySettingsPanel({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [settings, setSettings] = useState<MoneySettings | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { api.money().then((s) => { setSettings(s); setDraft({}); }).catch(() => {}); }, []);

  async function save() {
    const patch: Record<string, number | null> = {};
    for (const [k, v] of Object.entries(draft)) patch[k] = v.trim() === "" ? null : Number(v);
    try {
      const next = await api.saveMoney(patch);
      setSettings(next); setDraft({}); setError("");
      setSaved(true); setTimeout(() => setSaved(false), 1800);
      onSaved();
    } catch (e) { setError(String((e as Error).message)); }
  }

  return (
    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
      <GlassCard className="p-5">
        <p className="mb-4 text-sm text-muted">
          These are the rupee figures behind every number above. Put your real contract numbers in and
          everything recalculates. Leave a box empty to go back to our assumption.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          {settings && Object.values(settings).map((s) => (
            <div key={s.key}>
              <label className="flex items-center gap-2 text-sm">
                {s.label}
                <span title={s.basis} className="cursor-help text-faint hover:text-amber"><Info size={12} /></span>
                <Badge tone={s.source === "your number" ? "green" : "steel"}>{s.source}</Badge>
              </label>
              <p className="mb-1.5 mt-0.5 text-xs text-faint">{s.plain}</p>
              <div className="flex items-center gap-2">
                <span className="text-muted">₹</span>
                <input inputMode="numeric" placeholder={String(s.value)}
                  value={draft[s.key] ?? (s.source === "your number" ? String(s.value) : "")}
                  onChange={(e) => setDraft({ ...draft, [s.key]: e.target.value })}
                  className="w-full rounded-lg border border-line bg-black/30 px-3 py-1.5 font-mono text-sm
                    outline-none focus:border-amber/50" />
                <span className="shrink-0 text-xs text-faint">per day</span>
              </div>
            </div>
          ))}
        </div>
        {error && <p className="mt-3 text-sm text-red">{error}</p>}
        <div className="mt-4 flex items-center gap-3">
          <button onClick={save}
            className="rounded-lg bg-amber px-4 py-2 text-sm font-medium text-black transition hover:bg-amber-bright">
            Save my numbers
          </button>
          <button onClick={onClose} className="text-sm text-faint transition hover:text-text">Close</button>
          {saved && <span className="flex items-center gap-1 text-sm text-green"><Check size={14} /> saved</span>}
        </div>
      </GlassCard>
    </motion.div>
  );
}

/** Indian short form, mirroring the backend's fmt_inr for values the API
 *  hands over as raw numbers. */
export function fmtShort(n: number): string {
  const a = Math.abs(n), sign = n < 0 ? "-" : "";
  if (a >= 1e7) return `${sign}₹${(a / 1e7).toFixed(2).replace(/\.00$/, "")} crore`;
  if (a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(2).replace(/\.00$/, "")} lakh`;
  return `${sign}₹${Math.round(a).toLocaleString("en-IN")}`;
}
