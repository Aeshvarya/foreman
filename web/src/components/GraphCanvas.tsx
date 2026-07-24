import { useMemo } from "react";
import {
  ReactFlow, Background, BackgroundVariant, Handle, Position,
  type Node, type Edge, type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Project } from "../lib/api";

type State = "dim" | "delayed" | "slipped" | "handover-safe" | "handover-break";

const COL = { supplier: 0, material: 340, activity: 700 } as const;

/* Custom node — a pill that changes state during a cascade. The glow is the
   "light up what breaks" signature carried into the interactive graph. */
function FMNode({ data }: NodeProps) {
  const { label, name, state } = data as { label: string; name: string; state: State };
  const styles: Record<State, string> = {
    dim: "border-line bg-white/[0.03] text-muted",
    delayed: "border-amber bg-amber/15 text-amber shadow-[0_0_20px_-2px_rgba(245,166,35,0.6)]",
    slipped: "border-red bg-red/15 text-red shadow-[0_0_18px_-2px_rgba(229,72,77,0.55)]",
    "handover-safe": "border-green bg-green/15 text-green shadow-[0_0_18px_-2px_rgba(70,167,88,0.5)]",
    "handover-break": "border-red bg-red/20 text-red shadow-[0_0_22px_-2px_rgba(229,72,77,0.7)]",
  };
  return (
    <div className={`rounded-lg border px-3 py-1.5 font-mono text-[0.7rem] transition-all duration-500 ${styles[state]}`}
      title={name}>
      <Handle type="target" position={Position.Left} className="!border-0 !bg-transparent" />
      {label}
      <Handle type="source" position={Position.Right} className="!border-0 !bg-transparent" />
    </div>
  );
}
const nodeTypes = { fm: FMNode };

export default function GraphCanvas({
  project, delayedId, slippedIds, handoverBreaks,
}: {
  project: Project; delayedId?: string; slippedIds?: Set<string>; handoverBreaks?: boolean;
}) {
  const { nodes, edges } = useMemo(() => {
    const counters: Record<string, number> = { supplier: 0, material: 0, activity: 0 };
    const slipped = slippedIds ?? new Set<string>();

    const nodes: Node[] = project.nodes.map((n) => {
      const kind = n.kind as keyof typeof COL;
      const i = counters[kind]++;
      let state: State = "dim";
      if (n.id === delayedId) state = "delayed";
      else if (slipped.has(n.id)) state = "slipped";
      else if (n.id === project.handover) state = handoverBreaks ? "handover-break" : "handover-safe";
      return {
        id: n.id, type: "fm",
        position: { x: COL[kind], y: i * 62 },
        data: { label: n.id, name: n.name, state },
        draggable: false,
      };
    });

    const hot = new Set<string>([delayedId ?? "", ...slipped]);
    const edges: Edge[] = project.edges.map((e, i) => {
      const isHot = hot.has(e.source) && (hot.has(e.target) || e.target === project.handover);
      return {
        id: `e${i}`, source: e.source, target: e.target,
        animated: isHot,
        style: { stroke: isHot ? "var(--amber)" : "rgba(255,255,255,0.08)", strokeWidth: isHot ? 2 : 1 },
        type: "smoothstep",
      };
    });
    return { nodes, edges };
  }, [project, delayedId, slippedIds, handoverBreaks]);

  return (
    <div className="h-[440px] w-full overflow-hidden rounded-xl border border-line bg-black/20">
      <ReactFlow
        nodes={nodes} edges={edges} nodeTypes={nodeTypes}
        fitView fitViewOptions={{ padding: 0.15 }}
        nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
        proOptions={{ hideAttribution: true }} minZoom={0.3}>
        <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="rgba(255,255,255,0.06)" />
      </ReactFlow>
    </div>
  );
}
