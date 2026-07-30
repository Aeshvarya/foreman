import { useEffect } from "react";
import { useParams } from "react-router-dom";
import Sidebar from "../components/dashboard/Sidebar";
import ErrorBoundary from "../components/ErrorBoundary";
import { useProject } from "../lib/useProject";
import { useTour } from "../features/tour/TourProvider";
import { TourTarget } from "../features/tour/TourTarget";
import { TOURS } from "../features/tour/tours";
import Today from "../tools/Today";
import Cascade from "../tools/Cascade";
import Radar from "../tools/Radar";
import Ask from "../tools/Ask";
import Build from "../tools/Build";
import NewProject from "../tools/NewProject";

const TOOLS: Record<string, { title: string; sub: string; el: React.FC }> = {
  today: { title: "Today", sub: "What needs you right now — read for you, in plain English.", el: Today },
  cascade: { title: "Delay Cascade Simulator", sub: "Say something's running late and see exactly what it breaks — and what the fix costs.", el: Cascade },
  radar: { title: "Risk Radar", sub: "How much each delivery can slip before your handover date moves.", el: Radar },
  ask: { title: "Ask Foreman", sub: "Ask about the project in your own words, and watch it work the answer out.", el: Ask },
  build: { title: "Build from Docs", sub: "Point it at your emails and delivery notes — it reads them and builds the picture.", el: Build },
  new: { title: "New Project", sub: "Describe your project in a sentence, or upload the spreadsheet you already have.", el: NewProject },
};

export default function Dashboard() {
  // Landing on the dashboard should answer "what needs me?" before it offers
  // tools to drive — so the default is the brief, not the simulator.
  const { tool = "today" } = useParams();
  const { project } = useProject();
  const { start, steps: activeTour } = useTour();
  const active = TOOLS[tool] ?? TOOLS.today;
  const Tool = active.el;

  // First-ever dashboard visit → spotlight tour of the shell (project switcher,
  // tool list, live KPIs). Waits for the project to load so targets are real,
  // and for any other tour (e.g. the current tool's own) to finish first —
  // re-fires once that clears, so a same-tick race never drops this tour.
  useEffect(() => {
    if (!project || activeTour) return;
    const t = setTimeout(() => start("dashboard-shell", TOURS["dashboard-shell"]), 200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [!!project, !!activeTour]);

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-x-hidden">
        <header className="flex items-center justify-between border-b border-line px-8 py-5">
          <div>
            <h1 className="font-display text-xl font-bold">{active.title}</h1>
            <p className="mt-0.5 text-sm text-muted">{active.sub}</p>
          </div>
          {project && (
            <TourTarget name="shell-kpis" className="hidden items-center gap-6 md:flex">
              {[
                [project.counts.suppliers, "suppliers"],
                [project.counts.materials, "materials"],
                [project.counts.activities, "jobs on site"],
                [project.counts.edges, "connections"],
              ].map(([v, l]) => (
                <div key={l} className="text-right">
                  <div className="font-display text-lg font-bold leading-none">{v}</div>
                  <div className="kicker mt-1">{l}</div>
                </div>
              ))}
            </TourTarget>
          )}
        </header>
        <div className="px-8 py-7">
          <ErrorBoundary key={tool}>
            <Tool />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}
