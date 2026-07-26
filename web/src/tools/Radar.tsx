import { useEffect, useState } from "react";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { api, type RiskItem, type MonteCarlo } from "../lib/api";
import { GlassCard, Badge, Kicker } from "../components/primitives";
import { cn } from "../lib/cn";
import { useTour } from "../features/tour/TourProvider";
import { TourTarget } from "../features/tour/TourTarget";
import { TOURS } from "../features/tour/tours";

function tone(verdict: string): { tone: "red" | "amber" | "green" | "steel"; label: string } {
  const label = verdict.replace(/^[^\w]+/, "").split("—")[0].trim();
  if (verdict.startsWith("🔴")) return { tone: "red", label };
  if (verdict.startsWith("🟠")) return { tone: "amber", label };
  if (verdict.startsWith("🟡")) return { tone: "amber", label };
  return { tone: "green", label };
}
const barColor = (t: string) => ({ red: "var(--red)", amber: "var(--amber)", green: "var(--green)", steel: "var(--steel)" }[t]!);

export default function Radar() {
  const [risk, setRisk] = useState<RiskItem[]>([]);
  const [mc, setMc] = useState<MonteCarlo | null>(null);
  const { start, steps: activeTour } = useTour();

  useEffect(() => {
    api.risk().then(setRisk).catch(() => {});
    api.montecarlo().then(setMc).catch(() => {});
  }, []);

  // First-ever visit → spotlight tour, once both the Monte-Carlo headline and
  // the ranking have data, and no other tour is still running — re-fires once
  // that clears, so a same-tick race with another tour never drops this one.
  useEffect(() => {
    if (!mc || risk.length === 0 || activeTour) return;
    const t = setTimeout(() => start("radar", TOURS.radar), 200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [!!mc, risk.length > 0, !!activeTour]);

  const breaks = mc && mc.p_slip >= 0.25;

  return (
    <div className="mx-auto max-w-[980px]">
      {!mc && risk.length === 0 && (
        <div className="py-16 text-center text-sm text-muted">
          <span className="animate-pulse">running the risk model across 3,000 simulations…</span>
        </div>
      )}
      {/* Monte-Carlo headline */}
      {mc && (
        <TourTarget name="radar-mc">
        <GlassCard className={cn("mb-8 flex items-start gap-4 p-6", breaks ? "border-red/30" : "border-green/25")}>
          <div className={cn("mt-0.5", breaks ? "text-red" : "text-green")}>
            {breaks ? <ShieldAlert size={26} /> : <ShieldCheck size={26} />}
          </div>
          <div>
            <div className="font-display text-2xl font-bold">
              Monte-Carlo: <span className={breaks ? "text-red" : "text-green"}>{Math.round(mc.p_slip * 100)}%</span> chance the handover slips
            </div>
            <div className="mt-1.5 text-sm text-muted">
              across {mc.n.toLocaleString()} simulations · expected {mc.mean_slip}d, P90 {mc.p90_slip}d
              {mc.drivers[0]?.risk_contribution > 0 && <> · biggest driver: <span className="text-text">{mc.drivers[0].name}</span></>}
            </div>
          </div>
        </GlassCard>
        </TourTarget>
      )}

      <TourTarget name="radar-ranking">
        <Kicker className="mb-4">Silent-killer ranking · breaking point × confidence</Kicker>
      </TourTarget>
      <div className="flex flex-col gap-3">
        {risk.map((r) => {
          const { tone: t, label } = tone(r.verdict);
          const pct = r.breaking_point_days === null ? 100 : Math.max(6, Math.round((r.breaking_point_days / 45) * 100));
          const bp = r.breaking_point_days === null ? "no break within 45d" : `breaks handover after ${r.breaking_point_days} days`;
          return (
            <GlassCard key={r.material_id} hover className="p-5">
              <div className="flex items-center justify-between gap-3">
                <Badge tone={t}>{label}</Badge>
                <span className="font-mono text-xs text-faint">risk {r.risk_score}</span>
              </div>
              <div className="mt-3 font-display text-lg font-bold">
                {r.name} <span className="font-sans text-sm font-normal text-faint">· {r.material_id} · {r.supplier}</span>
              </div>
              <div className="mt-1 text-sm text-muted">
                {bp} · confidence <b className="text-text">{Math.round(r.confidence * 100)}%</b>
                <span className="text-faint"> ({r.confidence_source})</span>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/5">
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: barColor(t) }} />
              </div>
            </GlassCard>
          );
        })}
      </div>
    </div>
  );
}
