import { NavLink, useParams } from "react-router-dom";
import { Zap, Radar, MessageSquareText, FileStack, ArrowLeft, CircleHelp, Sun } from "lucide-react";
import { Wordmark } from "../primitives";
import ProjectSwitcher from "./ProjectSwitcher";
import { cn } from "../../lib/cn";
import { useTour } from "../../features/tour/TourProvider";
import { TourTarget } from "../../features/tour/TourTarget";
import { TOOL_TOUR_ID, TOURS } from "../../features/tour/tours";

const TOOLS = [
  { slug: "today", label: "Today", icon: Sun },
  { slug: "cascade", label: "Cascade Simulator", icon: Zap },
  { slug: "radar", label: "Risk Radar", icon: Radar },
  { slug: "ask", label: "Ask Foreman", icon: MessageSquareText },
  { slug: "build", label: "Build from Docs", icon: FileStack },
];

export default function Sidebar() {
  const { tool = "cascade" } = useParams();
  const { restart } = useTour();

  function replayTutorial() {
    const id = TOOL_TOUR_ID[tool] ?? "cascade";
    restart(id, TOURS[id]);
  }

  return (
    <aside className="sticky top-0 flex h-screen w-[248px] shrink-0 flex-col overflow-y-auto border-r border-line px-4 py-5">
      <div className="px-2"><Wordmark /></div>

      <div className="mt-6">
        <div className="kicker mb-2 px-2">Project</div>
        <TourTarget name="shell-project"><ProjectSwitcher /></TourTarget>
      </div>

      <TourTarget name="shell-tools" as="nav" className="mt-7 flex flex-col gap-1">
        <div className="kicker px-2 pb-2">Tools</div>
        {TOOLS.map((t) => (
          <NavLink key={t.slug} to={`/dashboard/${t.slug}`}
            className={({ isActive }) => cn(
              "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all",
              isActive
                ? "bg-amber/10 text-amber border border-amber/25"
                : "text-muted border border-transparent hover:bg-white/[0.03] hover:text-text",
            )}>
            <t.icon size={17} />
            {t.label}
          </NavLink>
        ))}
      </TourTarget>

      <div className="mt-auto flex flex-col gap-2 px-1">
        <button onClick={replayTutorial}
          className="flex items-center gap-2 px-2 text-sm text-faint transition hover:text-amber">
          <CircleHelp size={14} /> Replay tutorial
        </button>
        <NavLink to="/" className="flex items-center gap-2 px-2 text-sm text-faint hover:text-muted">
          <ArrowLeft size={14} /> Back to site
        </NavLink>
      </div>
    </aside>
  );
}
