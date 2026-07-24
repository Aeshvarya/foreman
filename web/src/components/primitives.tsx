import { Link } from "react-router-dom";
import { type ReactNode } from "react";
import { cn } from "../lib/cn";

/* Wordmark — a small amber schematic mark + the name. The mark echoes a
   supply-chain node lighting up, the product's core idea. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn("flex items-center gap-2.5 group", className)}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
        <circle cx="5" cy="12" r="2.4" fill="var(--steel)" />
        <circle cx="12" cy="6" r="2.4" fill="var(--steel)" />
        <circle cx="19" cy="12" r="3" fill="var(--amber)"
          className="group-hover:animate-pulse-node" />
        <circle cx="12" cy="18" r="2.4" fill="var(--steel)" />
        <path d="M5 12h7M12 6l7 6M12 18l7-6M12 6v12" stroke="var(--border-strong)" strokeWidth="1.2" />
        <path d="M12 6l7 6" stroke="var(--amber)" strokeWidth="1.6" />
      </svg>
      <span className="font-display text-[1.25rem] font-bold tracking-tight">
        FOREMAN<span className="text-amber">.</span>
      </span>
    </Link>
  );
}

export function Kicker({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("kicker", className)}>{children}</div>;
}

export function Button({
  children, to, href, variant = "primary", onClick, className, type,
}: {
  children: ReactNode; to?: string; href?: string;
  variant?: "primary" | "ghost"; onClick?: () => void; className?: string;
  type?: "button" | "submit";
}) {
  const base = cn(
    "inline-flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium",
    "transition-all duration-200 select-none",
    variant === "primary"
      ? "bg-amber text-black hover:bg-amber-bright hover:-translate-y-0.5 shadow-[0_4px_20px_-4px_rgba(245,166,35,0.5)]"
      : "border border-line-strong text-text hover:border-amber/50 hover:bg-surface",
    className,
  );
  if (to) return <Link to={to} className={base}>{children}</Link>;
  if (href) return <a href={href} className={base}>{children}</a>;
  return <button type={type ?? "button"} onClick={onClick} className={base}>{children}</button>;
}

export function GlassCard({
  children, className, hover = false,
}: { children: ReactNode; className?: string; hover?: boolean }) {
  return (
    <div className={cn(
      "glass rounded-xl shadow-panel",
      hover && "transition-all duration-200 hover:border-amber/30 hover:-translate-y-0.5",
      className,
    )}>{children}</div>
  );
}

export function StatTile({ value, label, accent }: { value: ReactNode; label: string; accent?: boolean }) {
  return (
    <GlassCard className="px-5 py-4 min-w-[130px]" hover>
      <div className={cn("font-display text-2xl font-bold leading-none", accent && "text-amber")}>{value}</div>
      <div className="kicker mt-2">{label}</div>
    </GlassCard>
  );
}

export function Badge({ children, tone = "steel" }: { children: ReactNode; tone?: "amber" | "red" | "green" | "steel" }) {
  const tones = {
    amber: "bg-amber/12 text-amber border-amber/30",
    red: "bg-red/12 text-red border-red/30",
    green: "bg-green/12 text-green border-green/30",
    steel: "bg-white/5 text-muted border-line",
  }[tone];
  return (
    <span className={cn(
      "inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[0.66rem] uppercase tracking-wider",
      tones,
    )}>{children}</span>
  );
}
