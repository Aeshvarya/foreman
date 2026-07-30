import { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Mic, MicOff, FileSpreadsheet, Sparkles, Loader2, AlertTriangle,
  Check, Package, Building2, ListChecks, Rocket,
} from "lucide-react";
import { api, type ProjectDraft } from "../lib/api";
import { GlassCard, Kicker, Badge } from "../components/primitives";
import { cn } from "../lib/cn";

/* "Tell me about your project" — the path in for someone who cannot start by
 * enumerating suppliers, materials and dependencies in a form.
 *
 * Three ways to say the same thing: type it, speak it, or hand over the
 * spreadsheet you already keep. All three land on the same draft screen, and
 * NOTHING is saved until the user looks at what we understood and agrees. A
 * schedule invented from a sentence has to be confirmed by a human before
 * anyone's decisions rest on it. */

const EXAMPLE =
  "40MW data centre in Chennai, handover 15 March 2027. Structural steel from " +
  "Tata Projects arriving mid-January, 4000A switchgear from Siemens, chillers " +
  "from Blue Star. Steel is confirmed, switchgear is not.";

export default function DescribeProject({ onCancel }: { onCancel?: () => void }) {
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<ProjectDraft | null>(null);
  const [busy, setBusy] = useState<"reading" | "creating" | null>(null);
  const [error, setError] = useState("");
  const [listening, setListening] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const recRef = useRef<any>(null);

  const speechSupported = typeof window !== "undefined" &&
    ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

  async function read() {
    setError(""); setBusy("reading");
    try { setDraft(await api.draftProject(text)); }
    catch (e) { setError(msg(e)); }
    finally { setBusy(null); }
  }

  async function readFile(file: File) {
    setError(""); setBusy("reading");
    try {
      const d = await api.draftProjectFromFile(file);
      setDraft(d);
      if (d.extracted && !text.trim()) setText(d.extracted.slice(0, 1500));
    } catch (e) { setError(msg(e)); }
    finally { setBusy(null); }
  }

  async function create() {
    if (!draft) return;
    setBusy("creating"); setError("");
    try {
      await api.createProject(draft.draft as never);
      window.location.assign("/dashboard/today");
    } catch (e) { setError(msg(e)); setBusy(null); }
  }

  /* Dictation runs entirely in the browser — no audio leaves the machine, and
     it costs nothing. On a noisy site, talking is more realistic than typing. */
  function toggleMic() {
    if (listening) { recRef.current?.stop(); setListening(false); return; }
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    const rec = new SR();
    rec.lang = "en-IN";
    rec.continuous = true;
    rec.interimResults = false;
    rec.onresult = (e: any) => {
      const said = Array.from(e.results).slice(e.resultIndex)
        .map((r: any) => r[0].transcript).join(" ");
      setText((t) => (t ? `${t} ${said}`.replace(/\s+/g, " ") : said.trimStart()));
    };
    rec.onerror = () => setListening(false);
    rec.onend = () => setListening(false);
    rec.start();
    recRef.current = rec;
    setListening(true);
  }

  return (
    <div className="flex flex-col gap-5">
      <GlassCard className="p-6">
        <Kicker>Step 1</Kicker>
        <h2 className="mt-1.5 font-display text-2xl font-bold">Tell me about your project</h2>
        <p className="mt-1.5 text-sm text-muted">
          Just describe it the way you would to a colleague. Foreman works out the suppliers,
          the materials and the order the jobs have to happen in.
        </p>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          placeholder={EXAMPLE}
          className="mt-4 w-full resize-y rounded-xl border border-line bg-black/30 p-4 text-sm
            leading-relaxed outline-none transition focus:border-amber/50"
        />

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button onClick={read} disabled={busy !== null || text.trim().length < 12}
            className="inline-flex items-center gap-2 rounded-lg bg-amber px-5 py-2.5 text-sm font-medium
              text-black transition hover:bg-amber-bright disabled:cursor-not-allowed disabled:opacity-40">
            {busy === "reading" ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
            {busy === "reading" ? "reading it…" : "Build my project"}
          </button>

          {speechSupported && (
            <button onClick={toggleMic}
              className={cn("inline-flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm transition",
                listening ? "border-red/50 bg-red/10 text-red" : "border-line-strong text-text hover:border-amber/50")}>
              {listening ? <MicOff size={15} /> : <Mic size={15} />}
              {listening ? "listening — tap to stop" : "or speak it"}
            </button>
          )}

          <button onClick={() => fileRef.current?.click()} disabled={busy !== null}
            className="inline-flex items-center gap-2 rounded-lg border border-line-strong px-4 py-2.5
              text-sm text-text transition hover:border-amber/50 disabled:opacity-40">
            <FileSpreadsheet size={15} /> or upload your spreadsheet
          </button>
          <input ref={fileRef} type="file" accept=".csv,.tsv,.txt,.xlsx,.xlsm" hidden
            onChange={(e) => { const f = e.target.files?.[0]; if (f) readFile(f); e.target.value = ""; }} />

          {!text && (
            <button onClick={() => setText(EXAMPLE)} className="text-sm text-faint transition hover:text-amber">
              use the example
            </button>
          )}
          {onCancel && (
            <button onClick={onCancel} className="ml-auto text-sm text-faint transition hover:text-text">
              I'd rather fill in a form
            </button>
          )}
        </div>

        {error && (
          <p className="mt-3 flex items-start gap-2 text-sm text-red">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" /> {error}
          </p>
        )}
      </GlassCard>

      <AnimatePresence>
        {draft && (
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}>
            <GlassCard className="border-amber/30 p-6">
              <Kicker>Step 2 — check this is right</Kicker>
              <h3 className="mt-1.5 font-display text-xl font-bold">
                Here's what I understood
              </h3>
              <p className="mt-1 text-sm text-muted">{draft.summary}</p>

              <div className="mt-5 grid gap-5 lg:grid-cols-3">
                <Column icon={Building2} title="Who supplies you"
                  rows={draft.draft.suppliers.map((s) => s.name)} />
                <Column icon={Package} title="What's coming"
                  rows={draft.draft.materials.map((m) => {
                    const sup = draft.draft.suppliers.find((s) => s.id === m.supplier);
                    return `${m.name} — ${sup?.name ?? "?"} · due ${m.expected_arrival}`;
                  })} />
                <Column icon={ListChecks} title="The order of work"
                  rows={draft.draft.activities.map((a, i) => `${i + 1}. ${a.name} (${a.duration_days} days)`)} />
              </div>

              {draft.warnings.length > 0 && (
                <div className="mt-5 rounded-xl border border-amber/25 bg-amber/[0.04] p-4">
                  <div className="flex items-center gap-2 text-amber">
                    <AlertTriangle size={14} /><span className="kicker !text-amber/90">I had to assume a few things</span>
                  </div>
                  <ul className="mt-2 flex flex-col gap-1.5">
                    {draft.warnings.map((w, i) => (
                      <li key={i} className="text-sm text-muted">• {w}</li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs text-faint">
                    You can change any of this later — nothing here is locked in.
                  </p>
                </div>
              )}

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <button onClick={create} disabled={busy !== null}
                  className="inline-flex items-center gap-2 rounded-lg bg-amber px-5 py-2.5 text-sm font-medium
                    text-black transition hover:bg-amber-bright disabled:opacity-40">
                  {busy === "creating" ? <Loader2 size={15} className="animate-spin" /> : <Rocket size={15} />}
                  Looks right — start using it
                </button>
                <button onClick={() => setDraft(null)}
                  className="text-sm text-faint transition hover:text-text">
                  not quite — let me reword it
                </button>
                <Badge tone="steel">nothing saved yet</Badge>
              </div>
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Column({ icon: Icon, title, rows }: {
  icon: typeof Package; title: string; rows: string[];
}) {
  return (
    <div>
      <div className="mb-2.5 flex items-center gap-2 text-amber">
        <Icon size={14} /><span className="kicker !text-amber/90">{title}</span>
        <span className="text-xs text-faint">{rows.length}</span>
      </div>
      <ul className="flex flex-col gap-1.5">
        {rows.map((r, i) => (
          <li key={i} className="flex gap-2 text-sm text-muted">
            <Check size={13} className="mt-1 shrink-0 text-green/70" />{r}
          </li>
        ))}
      </ul>
    </div>
  );
}

function msg(e: unknown) {
  return e instanceof Error ? e.message : String(e);
}
