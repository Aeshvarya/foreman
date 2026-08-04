import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { History, TriangleAlert, EyeOff, Eye } from "lucide-react";
import { api, type Waiting } from "../lib/api";
import { GlassCard, Badge } from "../components/primitives";
import { cn } from "../lib/cn";

/* "What does waiting cost me?" — the panel that proves early warning is worth
 * something, rather than just claiming it.
 *
 * The bars are not decoration: each week's height is the real total bill if
 * you act then, and it climbs because recovery options physically expire. A
 * replacement supplier who needs 24 days is a real choice today and an
 * impossible one in three weeks, because the date they must hit has not moved. */

export default function CostOfWaiting({ materialId, delayDays }: {
  materialId: string; delayDays: number;
}) {
  const [data, setData] = useState<Waiting | null>(null);
  const [open, setOpen] = useState(true);

  useEffect(() => {
    if (!materialId) { setData(null); return; }
    let live = true;
    api.costOfWaiting(materialId, delayDays)
      .then((d) => live && setData(d))
      .catch(() => live && setData(null));
    return () => { live = false; };
  }, [materialId, delayDays]);

  if (!data) return null;

  if (data.safe) {
    return (
      <GlassCard className="border-green/25 p-5">
        <div className="flex items-center gap-2 text-green"><History size={15} />
          <span className="kicker !text-green/90">If you left it alone</span></div>
        <p className="mt-2 text-sm text-muted">{data.headline}</p>
      </GlassCard>
    );
  }

  const peak = Math.max(...data.checkpoints.map((c) => c.cost), 1);

  return (
    <GlassCard className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-amber">
            <History size={15} /><span className="kicker !text-amber/90">What waiting costs you</span>
          </div>
          <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-text">{data.headline}</p>
        </div>
        <button onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1.5 text-xs text-faint transition hover:text-amber">
          {open ? <EyeOff size={13} /> : <Eye size={13} />}{open ? "hide" : "show"} the weeks
        </button>
      </div>

      {/* the headline comparison — early warning, in days */}
      <div className="mt-4 flex flex-wrap items-stretch gap-3">
        <div className="flex-1 rounded-xl border border-green/25 bg-green/[0.04] p-4">
          <div className="kicker !text-green/80">Foreman is telling you</div>
          <div className="mt-1 font-display text-2xl font-bold text-green">today</div>
          <div className="mt-1 text-sm text-muted">
            while it still costs {data.act_now_label} to protect the date
          </div>
        </div>
        <div className="flex-1 rounded-xl border border-red/25 bg-red/[0.04] p-4">
          <div className="kicker !text-red/80">Without it you'd find out</div>
          <div className="mt-1 font-display text-2xl font-bold text-red">
            {data.discovered_without_foreman}
          </div>
          <div className="mt-1 text-sm text-muted">
            when the delivery doesn't turn up — {data.warning_days} days from now
          </div>
        </div>
      </div>

      {open && (
        <div className="mt-5">
          {/* One shared baseline: every bar sits in a fixed-height track and
              grows from the bottom, so the heights are actually comparable. */}
          <div className="flex gap-2">
            {data.checkpoints.map((c, i) => {
              const gone = c.option === null;
              return (
                <div key={c.week} className="flex flex-1 flex-col items-center">
                  <div className={cn("mb-1.5 font-mono text-xs", gone ? "text-red" : "text-muted")}>
                    {c.cost_label}
                  </div>
                  <div className="flex h-[132px] w-full items-end border-b border-line">
                    <motion.div
                      initial={{ height: 4 }}
                      animate={{ height: `${Math.max(6, (c.cost / peak) * 128)}px` }}
                      transition={{ duration: 0.5, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
                      className={cn("w-full rounded-t-md border-t-2",
                        gone ? "border-red bg-red/25"
                          : i === 0 ? "border-green bg-green/25"
                            : "border-amber bg-amber/20")}
                      title={c.option ?? "nothing left that buys the date back"}
                    />
                  </div>
                  <div className="mt-2 text-center">
                    <div className={cn("text-xs", i === 0 ? "text-text" : "text-faint")}>{c.label}</div>
                    <div className="mt-0.5 hidden text-[0.65rem] leading-tight text-faint sm:block">
                      {gone ? "nothing left" : shorten(c.option!)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {data.options_expire && (
            <p className="mt-4 flex items-start gap-2 rounded-lg border border-amber/25 bg-amber/[0.04] p-3
              text-sm text-muted">
              <TriangleAlert size={14} className="mt-0.5 shrink-0 text-amber" />
              {data.options_expire}
            </p>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-faint">
            <Badge tone="steel">why it climbs</Badge>
            a replacement supplier needs the same lead time whenever you call them — but the date
            they have to hit doesn't move, so every week you wait removes options rather than adding them.
          </div>
        </div>
      )}
    </GlassCard>
  );
}

function shorten(s: string, n = 34) {
  return s.length <= n ? s : s.slice(0, n - 1).trimEnd() + "…";
}
