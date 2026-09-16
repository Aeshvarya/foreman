import { useRef, useState } from "react";
import { FileUp, X } from "lucide-react";
import { cn } from "../lib/cn";

/** A file slot you can click or drop onto, showing what's in it. */
export default function FilePick({ label, hint, accept, file, onFile, optional }: {
  label: string; hint: string; accept: string; file: File | null;
  onFile: (f: File | null) => void; optional?: boolean;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) onFile(f); }}
      className={cn("rounded-xl border border-dashed bg-black/20 p-4 transition",
        over ? "border-amber bg-amber/[0.06]" : "border-line-strong")}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="kicker">{label}{optional && <span className="ml-1 normal-case tracking-normal text-faint">(optional)</span>}</div>
          <div className="mt-1 truncate text-sm">
            {file ? <>{file.name} <span className="text-faint">· {(file.size / 1_000_000).toFixed(1)} MB</span></>
              : <span className="text-faint">{hint} — or drop it here</span>}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {file && (
            <button onClick={() => onFile(null)} aria-label={`remove ${label}`}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-faint transition hover:text-red">
              <X size={14} />
            </button>
          )}
          <button onClick={() => ref.current?.click()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong px-3 py-1.5 text-xs text-text transition hover:border-amber/50">
            <FileUp size={13} />{file ? "change" : "choose"}
          </button>
        </div>
      </div>
      <input ref={ref} type="file" accept={accept} hidden
        onChange={(e) => { onFile(e.target.files?.[0] ?? null); e.target.value = ""; }} />
    </div>
  );
}
