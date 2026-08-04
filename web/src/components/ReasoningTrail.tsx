import { useState } from "react";
import { motion } from "framer-motion";
import {
  Ear, Database, Search, GitBranch, CircleCheck, ShieldCheck,
  MessageSquareQuote, Ban, RefreshCw, Code2,
} from "lucide-react";
import type { TraceStep } from "../lib/api";
import { cn } from "../lib/cn";

/** How Foreman worked an answer out, shown as a readable trail.
 *
 * The old version was a collapsed "reasoning trace" printing raw step names and
 * Cypher — honest, but only legible to someone who knows what Cypher is. A site
 * manager closed it; a judge had to squint at it. This shows the SAME recorded
 * steps twice over: plain English by default, with the technical detail one
 * toggle away. Nothing is invented for the display — every line here is a step
 * the agent actually recorded, in the order it happened.
 *
 * The stagger is a reveal of finished work, not a fake progress bar: the answer
 * has already arrived by the time this renders.
 */

const ICONS: Record<string, typeof Ear> = {
  classify: Ear,
  cypher: Database,
  execute: Search,
  decompose: GitBranch,
  "sub-answer": CircleCheck,
  reflect: ShieldCheck,
  answer: MessageSquareQuote,
};

/** Steps worth calling out in colour — the two that make the reasoning visible. */
const HIGHLIGHT = new Set(["decompose", "reflect"]);

function iconFor(step: string, detail: string) {
  if (step === "execute" && detail.startsWith("BLOCKED")) return Ban;
  if (step === "execute" && (detail.includes("retry") || detail.includes("0 rows"))) return RefreshCw;
  return ICONS[step] ?? CircleCheck;
}

/** One-line summary of the depth of reasoning, for people who won't read the trail. */
function summarise(trace: TraceStep[]) {
  const queries = trace.filter((s) => s.step === "cypher" || s.step === "sub-answer").length;
  const subs = trace.filter((s) => s.step === "sub-answer").length;
  const checked = trace.some((s) => s.step === "reflect");
  const revised = trace.some((s) => s.detail.startsWith("gap:"));
  const bits = [`${queries} graph ${queries === 1 ? "query" : "queries"}`];
  if (subs) bits.push(`${subs} follow-up ${subs === 1 ? "question" : "questions"}`);
  if (checked) bits.push(revised ? "self-checked · found a gap and fixed it" : "self-checked");
  return bits.join(" · ");
}

export default function ReasoningTrail({ trace, mode }: { trace: TraceStep[]; mode: string }) {
  const [tech, setTech] = useState(false);
  if (!trace.length) return null;

  return (
    <div className="mt-4 border-t border-line pt-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="kicker text-amber/80">How Foreman worked this out</div>
          <div className="mt-0.5 text-xs text-faint">{summarise(trace)}</div>
        </div>
        <button
          onClick={() => setTech((t) => !t)}
          className={cn(
            "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[0.7rem] transition",
            tech
              ? "border-amber/40 bg-amber/10 text-amber"
              : "border-line text-muted hover:border-amber/40 hover:text-text",
          )}
        >
          <Code2 size={12} />
          {tech ? "Hide" : "Show"} technical detail
        </button>
      </div>

      <ol className="relative flex flex-col gap-0">
        {trace.map((s, i) => {
          const Icon = iconFor(s.step, s.detail);
          const hot = HIGHLIGHT.has(s.step);
          const last = i === trace.length - 1;
          return (
            <motion.li
              key={i}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.28, delay: i * 0.07, ease: [0.16, 1, 0.3, 1] }}
              className="relative flex gap-3 pb-3"
            >
              {/* connector */}
              {!last && <span className="absolute left-[11px] top-6 h-full w-px bg-line" />}
              <span
                className={cn(
                  "relative z-10 mt-0.5 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border",
                  hot
                    ? "border-amber/50 bg-amber/15 text-amber"
                    : "border-line bg-elev text-muted",
                )}
              >
                <Icon size={12} />
              </span>
              <div className="min-w-0 flex-1">
                <p className={cn("text-[0.84rem] leading-relaxed", hot ? "text-text" : "text-muted")}>
                  {s.say || s.detail}
                </p>
                {tech && (
                  <div className="mt-1.5 rounded-lg border border-line bg-black/30 p-2.5">
                    <div className="kicker mb-1 text-amber/70">{s.step}</div>
                    <code className="block whitespace-pre-wrap break-words font-mono text-[0.7rem] leading-relaxed text-steel-bright">
                      {s.detail}
                    </code>
                  </div>
                )}
              </div>
            </motion.li>
          );
        })}
      </ol>

      {tech && (
        <div className="mt-1 text-[0.7rem] text-faint">
          Answered by the <span className="font-mono text-muted">{mode}</span> agent. Every
          query above is read-only — Foreman can never write to the project graph.
        </div>
      )}
    </div>
  );
}
