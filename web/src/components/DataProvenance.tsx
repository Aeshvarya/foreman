import { useState } from "react";
import { FlaskConical, ChevronDown } from "lucide-react";
import { cn } from "../lib/cn";

/** Says out loud that the demo project is invented — and that the market
 * conditions behind it are not.
 *
 * Two things are true at once and both need saying. The project (Sunrise DC-1,
 * its suppliers, its dates) is synthetic: we had no access to a real feed, and
 * quietly showing invented data as if it were real would be the one thing that
 * should sink a project like this. But the *situation* it models is real, and
 * checkable — the long-lead items in this demo are the two most constrained
 * categories in the 2026 market, and a reader who works in data centers will
 * recognise the numbers below.
 *
 * The schedule is deliberately compressed so a whole build fits on one screen.
 * Saying so, unprompted, is cheaper than being asked.
 */

const MARKET: { item: string; real: string; note: string }[] = [
  {
    item: "Medium-voltage switchgear",
    real: "52–80 weeks",
    note: "effectively sold out through 2028 in many channels",
  },
  {
    item: "Large diesel generators",
    real: "60 weeks",
    note: "up from ~20 weeks pre-2020; major suppliers booked into 2028",
  },
  {
    item: "Substation transformers",
    real: "160+ weeks",
    note: "largest high-voltage units running up to four years",
  },
];

export default function DataProvenance() {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-6 rounded-xl border border-amber/25 bg-amber/[0.06]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2.5 px-4 py-2.5 text-left"
      >
        <FlaskConical size={14} className="shrink-0 text-amber" />
        <span className="text-[0.82rem] text-text">
          <strong className="font-semibold">This is a synthetic demo project.</strong>{" "}
          <span className="text-muted">
            The build, suppliers and dates are invented — the market lead times behind
            them are real.
          </span>
        </span>
        <ChevronDown
          size={14}
          className={cn("ml-auto shrink-0 text-muted transition", open && "rotate-180")}
        />
      </button>

      {open && (
        <div className="border-t border-amber/20 px-4 py-3.5">
          <p className="mb-3 text-[0.8rem] leading-relaxed text-muted">
            We had no access to a live project feed, so Sunrise DC-1 is invented. Its
            timeline is also compressed, so an entire data-center build fits on one
            screen. What is <em>not</em> invented is the squeeze it models — these are
            the real 2026 lead times for the long-lead items in this demo:
          </p>
          <ul className="flex flex-col gap-1.5">
            {MARKET.map((m) => (
              <li key={m.item} className="flex flex-wrap items-baseline gap-x-2 text-[0.8rem]">
                <span className="text-text">{m.item}</span>
                <span className="font-mono text-amber">{m.real}</span>
                <span className="text-faint">— {m.note}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[0.75rem] text-faint">
            Sources: industry lead-time trackers and supplier capacity announcements,
            2026. Point Foreman at a real project any time — New Project takes a
            sentence, a spreadsheet, or your own documents.
          </p>
        </div>
      )}
    </div>
  );
}
