import { useMemo, useRef, useEffect, useState } from "react";
import {
  ReactFlow, Background, BackgroundVariant, Handle, Position, Panel,
  type Node, type Edge, type NodeProps, type ReactFlowInstance,
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
  const { label, name, state, clickable, faded } = data as
    { label: string; name: string; state: State; clickable: boolean; faded: boolean };
  const styles: Record<State, string> = {
    dim: "border-line-strong bg-elev/95 text-muted",
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
    <div className={`w-[172px] rounded-xl border px-3 py-2 backdrop-blur-sm transition-all duration-300 ${styles[state]} ${clickHint} ${faded ? "opacity-[0.28]" : "opacity-100"}`}>
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-line-strong" />
      {/* The name is what a site manager recognises; the database id (MAT-1)
          means nothing to them, so it is kept as the tooltip only. */}
      <div className="flex items-center gap-2" title={label}>
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${active ? "bg-current" : "bg-steel"}`} />
        <span className="truncate text-[0.72rem] font-semibold leading-tight">{name}</span>
      </div>
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

  // Stable content keys for the two highlight Sets (see the memo below).
  const delayedKey = [...(delayedIds ?? [])].sort().join(",");
  const slippedKey = [...(slippedIds ?? [])].sort().join(",");

  const { nodes, edges } = useMemo(() => {
    const counters: Record<string, number> = { supplier: 0, material: 0, activity: 0 };
    const heights = { supplier: 6, material: 8, activity: 12 };
    const slipped = slippedIds ?? new Set<string>();
    const delayed = delayedIds ?? new Set<string>();
    const tallest = Math.max(...Object.values(heights));

    // Focus mode: when something is delayed, fade everything not on the
    // active cascade so the eye follows what breaks (declutters the web).
    const focus = delayed.size > 0;
    const involved = new Set<string>([...delayed, ...slipped, project.handover]);
    const near = new Set<string>(involved);
    for (const e of project.edges)
      if (involved.has(e.source) || involved.has(e.target)) { near.add(e.source); near.add(e.target); }

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
        data: { label: n.id, name: shortName(n.name), state, clickable: kind === "material",
                faded: focus && !near.has(n.id) },
        draggable: false,
      };
    });

    const hot = new Set<string>([...delayed, ...slipped]);
    const edges: Edge[] = project.edges.map((e, i) => {
      const isHot = hot.has(e.source) && (hot.has(e.target) || e.target === project.handover);
      let cls = "fm-dim";
      if (isHot) cls = "fm-hot";
      else if (focus && !(near.has(e.source) && near.has(e.target))) cls = "fm-faint";
      return {
        id: `e${i}`, source: e.source, target: e.target,
        type: "default", animated: isHot, className: cls,
      };
    });
    return { nodes, edges };
    // Keyed on the Sets' CONTENTS, not their object identity: a caller that
    // rebuilds `new Set(...)` inline every render would otherwise invalidate
    // this memo forever, and React Flow silently drops its edges when fed new
    // nodes/edges array identities at that rate. Content keys make the rebuild
    // happen only when something really changed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, delayedKey, slippedKey, handoverBreaks]);

  // Belt-and-suspenders against the "blank until resize" React Flow race:
  // keep the instance and re-fit whenever the container actually resizes.
  const wrapRef = useRef<HTMLDivElement>(null);
  const rf = useRef<ReactFlowInstance | null>(null);

  // THE BLANK-GRAPH FIX. React Flow resolves each edge against its source and
  // target in its internal node store, and if an edge arrives before those
  // nodes are registered it is dropped — permanently, with no retry and no
  // error. Handing it nodes and edges in the same first commit hit that race
  // on roughly 1 in 3 loads: 26 nodes rendered, the edges <svg> present but
  // empty, and the graph read as "gone blank".
  //
  // So mount with nodes only, then hand over the edges on the next frame, once
  // the nodes are definitely registered.
  const [edgesReady, setEdgesReady] = useState(false);
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => rf.current?.fitView({ padding: 0.12 }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={wrapRef} className="relative h-[68vh] min-h-[560px] w-full overflow-hidden rounded-2xl border border-line bg-black/40">
      <div className="pointer-events-none absolute inset-0 z-[1]"
        style={{ background: "radial-gradient(ellipse 60% 55% at 55% 45%, rgba(245,166,35,0.06), transparent 65%)" }} />
      <div className="pointer-events-none absolute inset-0 z-[1]"
        style={{ boxShadow: "inset 0 0 160px 40px rgba(0,0,0,0.75)" }} />
      <ReactFlow
        nodes={nodes} edges={edgesReady ? edges : []} nodeTypes={nodeTypes}
        fitView fitViewOptions={{ padding: 0.12 }}
        nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
        onNodeClick={(_, node) => { if (materialIds.has(node.id)) onToggleMaterial?.(node.id); }}
        // Nodes are registered by the time onInit fires — release the edges on
        // the next frame (see the edgesReady comment above), and re-fit once
        // the container has actually painted.
        onInit={(inst) => {
          rf.current = inst;
          requestAnimationFrame(() => setEdgesReady(true));
          setTimeout(() => inst.fitView({ padding: 0.12 }), 60);
        }}
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
          {[["running late", "var(--amber)"], ["pushed back", "var(--red)"], ["handover", "var(--green)"], ["not affected", "var(--steel)"]].map(([l, c]) => (
            <span key={l} className="flex items-center gap-1.5 text-[0.68rem] text-muted">
              <span className="h-2 w-2 rounded-full" style={{ background: c as string }} />{l}
            </span>
          ))}
        </Panel>
      </ReactFlow>
    </div>
  );
}
