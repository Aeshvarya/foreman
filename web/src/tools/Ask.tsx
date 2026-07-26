import { useEffect, useState } from "react";
import { Send, Brain, ChevronDown } from "lucide-react";
import { api, type AskResult } from "../lib/api";
import { GlassCard, Badge, Kicker } from "../components/primitives";
import { cn } from "../lib/cn";
import { useTour } from "../features/tour/TourProvider";
import { TourTarget } from "../features/tour/TourTarget";
import { TOURS } from "../features/tour/tours";

const EXAMPLES = [
  "Which materials have confidence below 0.75?",
  "If the diesel generators are delayed, what activities are affected?",
  "What if the switchgear slips 12 days?",
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
      const res = await api.ask(q);
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
                <div className="flex items-center gap-2 text-sm text-muted">
                  <Brain size={16} className="animate-pulse text-amber" /> reasoning over the graph…
                </div>
              ) : t.res && (
                <>
                  <div className="whitespace-pre-wrap text-sm leading-relaxed">{t.res.answer}</div>
                  {t.res.citations.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {t.res.citations.map((c) => <Badge key={c} tone="amber">{c}</Badge>)}
                    </div>
                  )}
                  {t.res.trace.length > 0 && <Trace res={t.res} />}
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

function Trace({ res }: { res: AskResult }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-4 border-t border-line pt-3">
      <button onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 text-xs text-muted transition hover:text-text">
        <Brain size={13} className="text-amber" />
        <span className="kicker">reasoning trace · {res.mode}</span>
        <ChevronDown size={13} className={cn("transition", open && "rotate-180")} />
      </button>
      {open && (
        <div className="mt-3 flex flex-col gap-2">
          {res.trace.map((s, i) => (
            <div key={i} className="rounded-lg border border-line bg-black/30 p-3">
              <div className="kicker mb-1 text-amber/80">{s.step}</div>
              <code className="whitespace-pre-wrap font-mono text-xs text-steel-bright">{s.detail}</code>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
