import { useEffect } from "react";
import { useParams } from "react-router-dom";
import Sidebar from "../components/dashboard/Sidebar";
import ErrorBoundary from "../components/ErrorBoundary";
import { useProject } from "../lib/useProject";
import { useTour } from "../features/tour/TourProvider";
import { TourTarget } from "../features/tour/TourTarget";
import { TOURS } from "../features/tour/tours";
import Cascade from "../tools/Cascade";
import Radar from "../tools/Radar";
import Ask from "../tools/Ask";
import Build from "../tools/Build";
import NewProject from "../tools/NewProject";

const TOOLS: Record<string, { title: string; sub: string; el: React.FC }> = {
  cascade: { title: "Delay Cascade Simulator", sub: "Slip a material and watch what breaks.", el: Cascade },
  radar: { title: "Risk Radar", sub: "Every material's breaking point, crossed with confidence.", el: Radar },
  ask: { title: "Ask Foreman", sub: "Query the project in plain English — watch it reason.", el: Ask },
  build: { title: "Build from Docs", sub: "Construct the graph from raw project documents.", el: Build },
  new: { title: "New Project", sub: "Enter a project's data and start simulating — no files, no code.", el: NewProject },
};

export default function Dashboard() {
  const { tool = "cascade" } = useParams();
  const { project } = useProject();
  const { start, steps: activeTour } = useTour();
  const active = TOOLS[tool] ?? TOOLS.cascade;
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
                [project.counts.activities, "activities"],
                [project.counts.edges, "graph edges"],
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
