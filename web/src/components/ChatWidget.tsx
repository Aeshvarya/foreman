import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, X, Send, Brain, Eye } from "lucide-react";
import { api, type AskResult } from "../lib/api";
import { readScene } from "../lib/scene";
import { cn } from "../lib/cn";

const EXAMPLES = [
  "Which materials are most at risk?",
  "What if the switchgear slips 12 days?",
];

interface Msg { role: "user" | "bot"; text: string; res?: AskResult; loading?: boolean; }

/* Floating "Ask Foreman" assistant — available on every page, like the support
   bubbles on top-tier sites, but wired to the real reasoning brain. */
export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sceneActive, setSceneActive] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs, open]);

  // Re-check whenever the panel opens (and while it's open, on an interval —
  // sessionStorage writes from the Cascade tool don't trigger a re-render
  // here on their own) so the "reading your live simulator" hint stays true
  // to whatever's actually on screen right now.
  useEffect(() => {
    if (!open) return;
    const check = () => setSceneActive(!!readScene());
    check();
    const id = setInterval(check, 1000);
    return () => clearInterval(id);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  async function send(q: string) {
    if (!q.trim()) return;
    setInput("");
    setMsgs((m) => [...m, { role: "user", text: q }, { role: "bot", text: "", loading: true }]);
    try {
      const res = await api.ask(q, readScene());
      setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { role: "bot", text: res.answer, res } : x)));
    } catch {
      setMsgs((m) => m.map((x, i) => (i === m.length - 1
        ? { role: "bot", text: "I can't reach the brain right now — make sure the API is running." } : x)));
    }
  }

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.96 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="glass fixed bottom-24 right-6 z-[60] flex h-[540px] w-[min(380px,calc(100vw-3rem))] flex-col overflow-hidden rounded-2xl shadow-[0_20px_60px_-12px_rgba(0,0,0,0.7)]">
            {/* header */}
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-amber/30 bg-amber/10 text-amber">
                  <Sparkles size={16} />
                </span>
                <div>
                  <div className="font-display text-sm font-bold">Ask Foreman</div>
                  <div className="kicker !text-[0.6rem]">the reasoning brain</div>
                </div>
              </div>
              <button onClick={() => setOpen(false)} className="text-muted transition hover:text-text">
                <X size={18} />
              </button>
            </div>

            {sceneActive && (
              <div className="flex items-center gap-1.5 border-b border-amber/15 bg-amber/[0.06] px-4 py-1.5 text-[0.68rem] text-amber/90">
                <Eye size={11} /> reading your live Cascade Simulator selection
              </div>
            )}

            {/* messages */}
            <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
              {msgs.length === 0 && (
                <div className="text-sm text-muted">
                  Ask me anything about the project — I'll reason over the graph.
                  <div className="mt-3 flex flex-col gap-2">
                    {EXAMPLES.map((e) => (
                      <button key={e} onClick={() => send(e)}
                        className="rounded-lg border border-line bg-white/[0.02] px-3 py-2 text-left text-[0.8rem] text-muted transition hover:border-amber/40 hover:text-text">
                        {e}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {msgs.map((m, i) => m.role === "user" ? (
                <div key={i} className="ml-6 rounded-2xl rounded-br-sm border border-line-strong bg-white/[0.04] px-3 py-2 text-sm">
                  {m.text}
                </div>
              ) : (
                <div key={i} className="mr-2 rounded-2xl rounded-bl-sm border border-line bg-black/30 px-3 py-2.5 text-sm leading-relaxed">
                  {m.loading ? (
                    <span className="flex items-center gap-2 text-muted"><Brain size={14} className="animate-pulse text-amber" /> reasoning…</span>
                  ) : (
                    <>
                      <div className="whitespace-pre-wrap">{m.text}</div>
                      {m.res && m.res.citations.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {m.res.citations.map((c) => (
                            <span key={c} className="rounded-full border border-amber/30 bg-amber/10 px-2 py-0.5 font-mono text-[0.6rem] text-amber">{c}</span>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              ))}
            </div>

            {/* input */}
            <form onSubmit={(e) => { e.preventDefault(); send(input); }}
              className="flex items-center gap-2 border-t border-line p-2.5">
              <input value={input} onChange={(e) => setInput(e.target.value)}
                placeholder="Ask Foreman…"
                className="flex-1 bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-faint" />
              <button type="submit" className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber text-black transition hover:bg-amber-bright">
                <Send size={15} />
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>

      {/* the floating button */}
      <button onClick={() => setOpen((o) => !o)}
        aria-label="Ask Foreman"
        className={cn(
          "fixed bottom-6 right-6 z-[60] flex h-14 w-14 items-center justify-center rounded-full",
          "bg-amber text-black shadow-[0_8px_30px_-4px_rgba(245,166,35,0.6)]",
          "transition-all duration-200 hover:scale-105 hover:bg-amber-bright",
        )}>
        <AnimatePresence mode="wait">
          {open
            ? <motion.span key="x" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ opacity: 0 }}><X size={22} /></motion.span>
            : <motion.span key="s" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ opacity: 0 }}><Sparkles size={22} /></motion.span>}
        </AnimatePresence>
      </button>
    </>
  );
}
