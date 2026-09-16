import { useState } from "react";
import { FileCheck2, ChevronDown, AlertTriangle } from "lucide-react";
import type { ImportProvenance } from "../lib/api";
import { cn } from "../lib/cn";

/** Says where an imported project's numbers come from, next to the numbers.
 *
 * An imported schedule is only as good as its conversion, and some parts are
 * always approximated -- links inferred from dates when the file has none,
 * a placeholder confidence when there is no P&D log. That belongs on screen,
 * one click from every figure, not in a log file nobody opens. */
export default function ImportBanner({ p }: { p: ImportProvenance }) {
  const [open, setOpen] = useState(false);
  const warn = p.warnings.length > 0;
  return (
    <div className={cn("mb-6 rounded-xl border", warn ? "border-amber/25 bg-amber/[0.06]" : "border-line bg-white/[0.02]")}>
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2.5 px-4 py-2.5 text-left">
        <FileCheck2 size={14} className="shrink-0 text-amber" />
        <span className="min-w-0 text-[0.82rem] text-text">
          <strong className="font-semibold">Imported from {p.source}{p.pd_source ? ` + ${p.pd_source}` : ""}.</strong>{" "}
          <span className="text-muted">
            {p.counts.activities.toLocaleString()} activities · links: {p.links_source} · items: {p.materials_source}
            {p.handover.matches_p6 && " · starting schedule matches P6"}
          </span>
        </span>
        {warn && (
          <span className="ml-auto shrink-0 rounded-full border border-amber/30 px-2 py-0.5 font-mono text-[0.66rem] uppercase tracking-wider text-amber">
            {p.warnings.length} to know
          </span>
        )}
        <ChevronDown size={14} className={cn("shrink-0 text-muted transition", !warn && "ml-auto", open && "rotate-180")} />
      </button>
      {open && (
        <div className="border-t border-line px-4 py-3.5 text-[0.8rem] leading-relaxed">
          {p.warnings.map((w) => (
            <p key={w} className="mb-2 flex gap-2 text-text">
              <AlertTriangle size={13} className="mt-0.5 shrink-0 text-amber" />{w}
            </p>
          ))}
          <ul className="flex flex-col gap-1 text-muted">
            {p.notes.map((n) => <li key={n}>· {n}</li>)}
          </ul>
          <p className="mt-2 text-faint">
            Confidence: {p.confidence_source}. Handover: {p.handover.name}
            {p.handover.p6_finish && <> (P6 finish {p.handover.p6_finish})</>}. Imported {p.imported}.
          </p>
        </div>
      )}
    </div>
  );
}
