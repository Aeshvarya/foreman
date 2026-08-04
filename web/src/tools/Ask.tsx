import { useEffect, useState } from "react";
import { Send } from "lucide-react";
import { api, type AskResult, type Citation } from "../lib/api";
import { GlassCard, Kicker } from "../components/primitives";
import ReasoningTrail from "../components/ReasoningTrail";
import { useTour } from "../features/tour/TourProvider";
import { TourTarget } from "../features/tour/TourTarget";
import { TOURS } from "../features/tour/tours";
import { readScene } from "../lib/scene";
import Thinking from "../components/Thinking";

// Deliberately mixed: the first two are reasoning questions that trigger the
// deep path (break down -> gather -> self-check), the third is a fast lookup —
// so the difference in how hard Foreman works is visible in the trail. All
// phrased the way a site manager would actually say them, no ids or decimals.
const EXAMPLES = [
  "Which part of this project is most likely to slip, and why?",
  "Why are the diesel generators the biggest risk?",
  "When does the switchgear arrive and who's making it?",
];

interface Turn { q: string; res?: AskResult; loading?: boolean; }

const HISTORY_KEY = "foreman:askHistory";

function loadHistory(): Turn[] {
  try {
    return JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

export default function Ask() {
  // Switching dashboard tabs unmounts this component (Dashboard renders one
  // tool at a time) — read from sessionStorage so the conversation survives
  // that, instead of resetting every time the user comes back to this tab.
  const [turns, setTurns] = useState<Turn[]>(loadHistory);
  const [input, setInput] = useState("");
  const { start, steps: activeTour } = useTour();

  useEffect(() => {
    // Drop any turn still mid-flight — its in-progress request belongs to a
    // stale closure and will never resolve into this mount, so persisting it
    // would leave a permanently stuck "reasoning…" spinner on next visit.
    const settled = turns.filter((t) => !t.loading);
    try {
      sessionStorage.setItem(HISTORY_KEY, JSON.stringify(settled));
    } catch {
      /* sessionStorage unavailable — history just won't persist */
    }
  }, [turns]);

  // First-ever visit → spotlight tour of the examples + input bar, once no
  // other tour is still running — re-fires once that clears, so a same-tick
  // race with another tour never drops this one.
  useEffect(() => {
    if (activeTour) return;
    const t = setTimeout(() => start("ask", TOURS.ask), 200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [!!activeTour]);

  async function ask(q: string) {
    if (!q.trim()) return;
    setInput("");
    const idx = turns.length;
    setTurns((t) => [...t, { q, loading: true }]);
    try {
      const res = await api.ask(q, readScene());
      setTurns((t) => t.map((x, i) => (i === idx ? { q, res } : x)));
    } catch {
      setTurns((t) => t.map((x, i) => (i === idx ? { q, res: { answer: "The agent is unavailable — is the API running with a Gemini key?", citations: [], trace: [], mode: "query" } } : x)));
    }
  }

  return (
    <div className="mx-auto flex max-w-[820px] flex-col">
      {turns.length === 0 && (
        <TourTarget name="ask-examples">
          <Kicker className="mb-3">Try asking</Kicker>
          <div className="mb-6 flex flex-wrap gap-2">
            {EXAMPLES.map((e) => (
              <button key={e} onClick={() => ask(e)}
                className="rounded-lg border border-line bg-white/[0.02] px-3.5 py-2 text-sm text-muted transition-all hover:border-amber/40 hover:text-text">
                {e}
              </button>
            ))}
          </div>
        </TourTarget>
      )}

      <div className="flex flex-col gap-5">
        {turns.map((t, i) => (
          <div key={i} className="flex flex-col gap-3">
            <div className="self-end rounded-2xl rounded-br-sm border border-line-strong bg-white/[0.04] px-4 py-2.5 text-sm">
              {t.q}
            </div>
            <GlassCard className="p-5">
              {t.loading ? (
                <Thinking />
              ) : t.res && (
                <>
                  <div className="whitespace-pre-wrap text-sm leading-relaxed">{t.res.answer}</div>
                  {t.res.citations.length > 0 && <Citations items={t.res.citations} />}
                  {t.res.trace.length > 0 && (
                    <ReasoningTrail trace={t.res.trace} mode={t.res.mode} />
                  )}
                </>
              )}
            </GlassCard>
          </div>
        ))}
      </div>

      <TourTarget name="ask-input">
        <form onSubmit={(e) => { e.preventDefault(); ask(input); }}
          className="sticky bottom-6 mt-6 flex items-center gap-2 rounded-xl border border-line-strong bg-elev/90 p-2 backdrop-blur">
          <input value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Foreman about the project…"
            className="flex-1 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-faint" />
          <button type="submit" className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber text-black transition hover:bg-amber-bright">
            <Send size={16} />
          </button>
        </form>
      </TourTarget>
    </div>
  );
}


/** What the answer was built from — a footnote, not a headline.
 *
 * Names read in normal case: an all-caps "STRUCTURAL STEEL PACKAGE (ROOF +
 * MEZZANINE)" shouts at the reader. And a broad question can legitimately touch
 * a dozen nodes, which is reassuring as a count and unreadable as a wall of
 * chips — so the list collapses until asked to open.
 */
function Citations({ items }: { items: Citation[] }) {
  const [all, setAll] = useState(false);
  const LIMIT = 5;
  const shown = all ? items : items.slice(0, LIMIT);
  const hidden = items.length - shown.length;

  return (
    <div className="mt-3 flex flex-wrap items-center gap-1.5">
      <span className="kicker mr-0.5 text-faint">based on</span>
      {shown.map((c) => (
        <span
          key={c.id}
          title={c.id}
          className="rounded-full border border-amber/25 bg-amber/[0.08] px-2.5 py-0.5 text-[0.72rem] text-amber/90"
        >
          {c.name}
        </span>
      ))}
      {hidden > 0 && (
        <button
          onClick={() => setAll(true)}
          className="rounded-full border border-line px-2.5 py-0.5 text-[0.72rem] text-muted transition hover:border-amber/40 hover:text-text"
        >
          +{hidden} more
        </button>
      )}
    </div>
  );
}
