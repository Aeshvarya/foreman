import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronsUpDown, Check, Plus, FolderKanban, Trash2 } from "lucide-react";
import { api, type ProjectMeta } from "../../lib/api";
import { cn } from "../../lib/cn";

export default function ProjectSwitcher() {
  const [projects, setProjects] = useState<ProjectMeta[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const nav = useNavigate();

  useEffect(() => { api.projects().then(setProjects).catch(() => {}); }, []);
  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const active = projects.find((p) => p.active);

  async function activate(id: string) {
    if (busy) return;
    setBusy(true);
    await api.activateProject(id).catch(() => {});
    window.location.assign("/dashboard/cascade");  // hard reload so all tools refetch
  }
  async function remove(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm("Delete this project?")) return;
    await api.deleteProject(id).catch(() => {});
    window.location.assign("/dashboard/cascade");
  }

  return (
    <div ref={ref} className="relative px-1">
      <button onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 rounded-lg border border-line bg-white/[0.02] px-2.5 py-2 text-left transition hover:border-line-strong">
        <FolderKanban size={15} className="shrink-0 text-amber" />
        <span className="min-w-0 flex-1 truncate text-sm">{active?.name ?? "Loading…"}</span>
        <ChevronsUpDown size={14} className="shrink-0 text-faint" />
      </button>

      {open && (
        <div className="absolute left-1 right-1 top-full z-50 mt-1.5 overflow-hidden rounded-lg border border-line-strong bg-elev shadow-[0_16px_40px_-8px_rgba(0,0,0,0.7)]">
          <div className="max-h-64 overflow-y-auto p-1">
            {projects.map((p) => (
              <button key={p.id} onClick={() => activate(p.id)}
                className={cn("group flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition hover:bg-white/[0.04]",
                  p.active && "text-amber")}>
                {p.active ? <Check size={14} className="shrink-0" /> : <span className="w-3.5" />}
                <span className="min-w-0 flex-1 truncate">{p.name}</span>
                {!p.seed && (
                  <span onClick={(e) => remove(p.id, e)}
                    className="shrink-0 text-faint opacity-0 transition hover:text-red group-hover:opacity-100">
                    <Trash2 size={13} />
                  </span>
                )}
              </button>
            ))}
          </div>
          <button onClick={() => { setOpen(false); nav("/dashboard/new"); }}
            className="flex w-full items-center gap-2 border-t border-line px-3 py-2.5 text-sm text-amber transition hover:bg-amber/5">
            <Plus size={15} /> New project
          </button>
        </div>
      )}
    </div>
  );
}
