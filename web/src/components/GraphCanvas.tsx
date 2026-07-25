import { useMemo } from "react";
import {
  ReactFlow, Background, BackgroundVariant, Handle, Position, Panel,
  type Node, type Edge, type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Project } from "../lib/api";

type State = "dim" | "delayed" | "slipped" | "handover-safe" | "handover-break";

const COL = { supplier: 0, material: 460, activity: 940 } as const;
const GAP = 74;

/* A labelled pill that changes state during a cascade — the glow is the
   "watch what breaks light up" signature. Material pills are clickable: click
   one to slip it (far easier than a dropdown). */
function FMNode({ data }: NodeProps) {
  const { label, name, state, clickable } = data as
    { label: string; name: string; state: State; clickable: boolean };
  const styles: Record<State, string> = {
    dim: "border-line bg-elev/80 text-muted",
    delayed: "border-amber bg-amber/15 text-amber shadow-[0_0_26px_-2px_rgba(245,166,35,0.75)]",
    slipped: "border-red bg-red/15 text-red shadow-[0_0_22px_-2px_rgba(229,72,77,0.7)]",
    "handover-safe": "border-green bg-green/15 text-green shadow-[0_0_24px_-2px_rgba(70,167,88,0.6)]",
    "handover-break": "border-red bg-red/20 text-red shadow-[0_0_28px_-2px_rgba(229,72,77,0.85)]",
  };
  const active = state !== "dim";
  const clickHint = clickable && state !== "delayed"
    ? "cursor-pointer hover:border-amber/60 hover:bg-amber/[0.06] hover:shadow-[0_0_18px_-4px_rgba(245,166,35,0.55)]"
    : clickable ? "cursor-pointer" : "";
  return (
    <div className={`w-[168px] rounded-xl border px-3 py-2 backdrop-blur-sm transition-all duration-300 ${styles[state]} ${clickHint}`}>
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-line-strong" />
      <div className="flex items-center gap-2">
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${active ? "bg-current" : "bg-steel"}`} />
        <span className="font-mono text-[0.72rem] font-semibold">{label}</span>
      </div>
      <div className="mt-0.5 truncate pl-3.5 text-[0.66rem] leading-tight text-faint">{name}</div>
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-line-strong" />
    </div>
  );
}
const nodeTypes = { fm: FMNode };
const shortName = (n: string) => n.replace(/\s*\(.*?\)/, "").split(",")[0];

export default function GraphCanvas({
  project, delayedIds, slippedIds, handoverBreaks, onToggleMaterial,
}: {
  project: Project; delayedIds?: Set<string>; slippedIds?: Set<string>;
  handoverBreaks?: boolean; onToggleMaterial?: (id: string) => void;
}) {
  const materialIds = useMemo(
    () => new Set(project.nodes.filter((n) => n.kind === "material").map((n) => n.id)),
    [project]);

  const { nodes, edges } = useMemo(() => {
    const counters: Record<string, number> = { supplier: 0, material: 0, activity: 0 };
    const heights = { supplier: 6, material: 8, activity: 12 };
    const slipped = slippedIds ?? new Set<string>();
    const delayed = delayedIds ?? new Set<string>();
    const tallest = Math.max(...Object.values(heights));

    const nodes: Node[] = project.nodes.map((n) => {
      const kind = n.kind as keyof typeof COL;
      const i = counters[kind]++;
      const offset = ((tallest - heights[kind]) * GAP) / 2;
      let state: State = "dim";
      if (delayed.has(n.id)) state = "delayed";
      else if (slipped.has(n.id)) state = "slipped";
      else if (n.id === project.handover) state = handoverBreaks ? "handover-break" : "handover-safe";
      return {
        id: n.id, type: "fm",
        position: { x: COL[kind], y: offset + i * GAP },
        data: { label: n.id, name: shortName(n.name), state, clickable: kind === "material" },
        draggable: false,
      };
    });

    const hot = new Set<string>([...delayed, ...slipped]);
    const edges: Edge[] = project.edges.map((e, i) => {
      const isHot = hot.has(e.source) && (hot.has(e.target) || e.target === project.handover);
      return {
        id: `e${i}`, source: e.source, target: e.target,
        type: "default", animated: isHot,
        className: isHot ? "fm-hot" : "fm-dim",
      };
    });
    return { nodes, edges };
  }, [project, delayedIds, slippedIds, handoverBreaks]);

  return (
    <div className="relative h-[68vh] min-h-[560px] w-full overflow-hidden rounded-2xl border border-line bg-black/40">
      <div className="pointer-events-none absolute inset-0 z-[1]"
        style={{ background: "radial-gradient(ellipse 60% 55% at 55% 45%, rgba(245,166,35,0.06), transparent 65%)" }} />
      <div className="pointer-events-none absolute inset-0 z-[1]"
        style={{ boxShadow: "inset 0 0 160px 40px rgba(0,0,0,0.75)" }} />
      <ReactFlow
        nodes={nodes} edges={edges} nodeTypes={nodeTypes}
        fitView fitViewOptions={{ padding: 0.12 }}
        nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
        onNodeClick={(_, node) => { if (materialIds.has(node.id)) onToggleMaterial?.(node.id); }}
        // Re-fit after the container has actually painted — prevents the
        // "blank until resize/refresh" race where RF measures a 0-size box.
        onInit={(inst) => { setTimeout(() => inst.fitView({ padding: 0.12 }), 60); }}
        proOptions={{ hideAttribution: true }} minZoom={0.2} maxZoom={1.4}>
        <Background variant={BackgroundVariant.Dots} gap={26} size={1} color="rgba(255,255,255,0.05)" />
        <Panel position="top-left" className="!m-4 flex flex-col gap-2">
          <div className="flex gap-2">
            {["Suppliers", "Materials", "Schedule → Handover"].map((l) => (
              <span key={l} className="kicker rounded-md border border-line bg-elev/70 px-2.5 py-1 backdrop-blur">{l}</span>
            ))}
          </div>
          <span className="kicker !text-amber/80">↳ click materials to slip several at once</span>
        </Panel>
        <Panel position="bottom-right" className="!m-4 flex flex-wrap gap-3 rounded-lg border border-line bg-elev/70 px-3 py-2 backdrop-blur">
          {[["delayed", "var(--amber)"], ["on critical path", "var(--red)"], ["handover", "var(--green)"], ["absorbed by float", "var(--steel)"]].map(([l, c]) => (
            <span key={l} className="flex items-center gap-1.5 text-[0.68rem] text-muted">
              <span className="h-2 w-2 rounded-full" style={{ background: c as string }} />{l}
            </span>
          ))}
        </Panel>
      </ReactFlow>
    </div>
  );
}
