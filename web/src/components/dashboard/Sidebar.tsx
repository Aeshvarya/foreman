import { NavLink } from "react-router-dom";
import { Zap, Radar, MessageSquareText, FileStack, ArrowLeft } from "lucide-react";
import { Wordmark } from "../primitives";
import { cn } from "../../lib/cn";

const TOOLS = [
  { slug: "cascade", label: "Cascade Simulator", icon: Zap },
  { slug: "radar", label: "Risk Radar", icon: Radar },
  { slug: "ask", label: "Ask Foreman", icon: MessageSquareText },
  { slug: "build", label: "Build from Docs", icon: FileStack },
];

export default function Sidebar() {
  return (
    <aside className="flex w-[248px] shrink-0 flex-col border-r border-line px-4 py-5">
      <div className="px-2"><Wordmark /></div>

      <nav className="mt-9 flex flex-col gap-1">
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
      </nav>

      <div className="mt-auto flex flex-col gap-3 px-1">
        <div className="flex items-center gap-2 px-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-green" />
          </span>
          <span className="kicker">Live · Neo4j + Gemini</span>
        </div>
        <NavLink to="/" className="flex items-center gap-2 px-2 text-sm text-faint hover:text-muted">
          <ArrowLeft size={14} /> Back to site
        </NavLink>
      </div>
    </aside>
  );
}
