import { useEffect, useRef, useState } from "react";
import { FileStack, AlertTriangle, Loader2, UploadCloud, RotateCcw } from "lucide-react";
import { api, type BuildResult, type DocFile } from "../lib/api";
import { GlassCard, Button, Badge, Kicker } from "../components/primitives";
import { cn } from "../lib/cn";
import { useTour } from "../features/tour/TourProvider";
import { TourTarget } from "../features/tour/TourTarget";
import { TOURS } from "../features/tour/tours";

export default function Build() {
  const [res, setRes] = useState<BuildResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [docs, setDocs] = useState<DocFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const { start, steps: activeTour } = useTour();

  useEffect(() => { api.docs().then(setDocs).catch(() => {}); }, []);

  // First-ever visit → spotlight tour, once the corpus list has loaded and no
  // other tour is still running — re-fires once that clears, so a same-tick
  // race with another tour never drops this one.
  useEffect(() => {
    if (docs.length === 0 || activeTour) return;
    const t = setTimeout(() => start("build", TOURS.build), 200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docs.length > 0, !!activeTour]);

  async function run() {
    setLoading(true);
    try { setRes(await api.buildGraph()); } catch { /* ignore */ }
    setLoading(false);
  }

  async function upload(fileList: FileList | File[]) {
    const files = Array.from(fileList);
    if (!files.length) return;
    setUploadError(null);
    setUploading(true);
    try {
      const { docs } = await api.uploadDocs(files);
      setDocs(docs);
      setRes(null); // stale — the corpus changed, force a rebuild before showing results
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "upload failed");
    }
    setUploading(false);
  }

  async function reset() {
    const { docs } = await api.resetDocs();
    setDocs(docs);
    setRes(null);
  }

  return (
    <div className="mx-auto max-w-[900px]">
      <p className="mb-6 max-w-2xl text-sm leading-relaxed text-muted">
        Foreman doesn't need clean data. It reads the messy documents a real project
        generates — POs, supplier emails, GPS feeds, goods-received notes, submittal logs —
        and builds the confidence-scored knowledge graph itself, scoring every fact by how
        trustworthy its source is and flagging conflicts when documents disagree.
      </p>

      <TourTarget name="build-dropzone">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); upload(e.dataTransfer.files); }}
        onClick={() => fileInput.current?.click()}
        className={cn(
          "mb-4 flex cursor-pointer flex-col items-center gap-2 rounded-2xl border border-dashed p-6 text-center transition-colors",
          dragOver ? "border-amber/60 bg-amber/5" : "border-line-strong hover:border-amber/40 hover:bg-surface",
        )}
      >
        <input
          ref={fileInput} type="file" accept=".txt" multiple className="hidden"
          onChange={(e) => e.target.files && upload(e.target.files)}
        />
        {uploading
          ? <Loader2 size={20} className="animate-spin text-amber" />
          : <UploadCloud size={20} className="text-muted" />}
        <div className="text-sm text-muted">
          Drop a project document here, or click to browse — plain text (.txt) only
        </div>
      </div>
      </TourTarget>
      {uploadError && (
        <div className="mb-4 text-sm text-red">{uploadError}</div>
      )}

      {docs.length > 0 && (
        <TourTarget name="build-doclist" className="mb-6 flex flex-col gap-1.5">
          <Kicker>Corpus for next build ({docs.length} doc{docs.length === 1 ? "" : "s"})</Kicker>
          {docs.map((d) => (
            <div key={d.name} className="flex items-center gap-2 text-xs text-muted">
              <span className={cn("font-mono", !d.seed && "text-amber")}>{d.name}</span>
              {!d.seed && <Badge tone="amber">uploaded</Badge>}
            </div>
          ))}
          {docs.some((d) => !d.seed) && (
            <button
              onClick={reset}
              className="mt-1 flex w-fit items-center gap-1.5 text-xs text-muted underline decoration-dotted hover:text-text"
            >
              <RotateCcw size={12} /> reset to demo corpus
            </button>
          )}
        </TourTarget>
      )}

      <TourTarget name="build-button">
      <Button onClick={run}>
        {loading ? <><Loader2 size={16} className="animate-spin" /> reading documents…</> : <><FileStack size={16} /> Build graph from documents</>}
      </Button>
      </TourTarget>

      {res && (
        <div className="mt-8">
          <div className="grid grid-cols-3 gap-3">
            {[[res.docs, "documents read"], [res.facts, "facts extracted"],
              [res.conflicts.length, "conflicts caught", res.conflicts.length > 0]].map(([v, l, hot]) => (
              <GlassCard key={l as string} className="p-5">
                <div className={cn("font-display text-3xl font-bold", hot ? "text-red" : "text-text")}>{v as number}</div>
                <div className="kicker mt-1.5">{l as string}</div>
              </GlassCard>
            ))}
          </div>

          {res.conflicts.map((c, i) => (
            <GlassCard key={i} className="mt-4 flex items-start gap-3 border-red/30 p-5">
              <AlertTriangle size={20} className="mt-0.5 shrink-0 text-red" />
              <div className="text-sm">
                <b>Conflict on {c.material} · {c.attribute}</b>
                <div className="mt-1 text-muted">
                  kept <b className="text-text">{c.kept.value}</b> ({c.kept.source}) over{" "}
                  <b className="text-text">{c.rejected[0].value}</b> ({c.rejected[0].source}) →
                  confidence lowered to <b className="text-amber">{Math.round(c.confidence * 100)}%</b> and flagged for human check
                </div>
              </div>
            </GlassCard>
          ))}

          <Kicker className="mb-3 mt-8">Confidence built from source evidence</Kicker>
          <div className="flex flex-col gap-2.5">
            {Object.entries(res.materials).sort().map(([mid, m]) => {
              const pct = Math.round(m.confidence * 100);
              const col = pct < 70 ? "var(--red)" : pct < 85 ? "var(--amber)" : "var(--green)";
              return (
                <GlassCard key={mid} className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="font-display font-bold">
                      {mid} <span className="font-sans text-sm font-normal text-muted">· {pct}% confidence</span>
                      {m.conflict && <span className="ml-2"><Badge tone="red">conflict</Badge></span>}
                    </div>
                  </div>
                  <div className="mt-1 text-xs text-faint">{m.confidence_source}</div>
                  <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-white/5">
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: col }} />
                  </div>
                </GlassCard>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
