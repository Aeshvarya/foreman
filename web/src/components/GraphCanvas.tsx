import { useMemo, useRef, useEffect, useState } from "react";
import {
  ReactFlow, Background, BackgroundVariant, Handle, Position, Panel,
  type Node, type Edge, type NodeProps, type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Project } from "../lib/api";

type State = "dim" | "delayed" | "slipped" | "handover-safe" | "handover-break";
type Kind = "supplier" | "material" | "activity";

const COL = { supplier: 0, material: 460, activity: 940 } as const;
const GAP = 74;

/* Above this many activities the whole web stops being readable (and React
   Flow stops being fast): a real P6 schedule is 1,000+ activities and would be
   a column 100,000 px tall. So large projects switch to TRACE mode — only the
   selected P&D items, what they feed, and the path of pushed-back activities
   to handover. The bundled demo has 12 activities and keeps the full view. */
const LARGE_AT = 40;
/* A traced path keeps where the item lands (+1 step) and the last steps into
   handover, and folds the middle into one "N more" node — so a 1,000-step
   chain still fits on one screen at a readable zoom. */
const PATH_HEAD = 3;
const PATH_TAIL = 3;
/* By default trace mode draws the slipped P&D items that push back the most
   work, and says how many it left out; "Show all" draws every one. Past about
   a dozen rows the fitted view gets too small to read, hence the default. */
const TOP_TRACED = 12;
/* Trace-mode spacing: wider columns and taller rows than the full view, so a
   path reads left → right instead of as a dense stack. */
const T_GAP = 96, T_STEP = 230, T_ACT_X = 260;
/* When the handover holds, how many absorbed-but-pushed-back activities to show
   downstream of each item before stopping. */
const SIDE_CAP = 8;

const KIND_TAG: Record<Kind, string> = { supplier: "Supplier", material: "P&D item", activity: "Activity" };

/* A labelled pill that changes state during a cascade — the glow is the
   "watch what breaks light up" signature. Material pills are clickable: click
   one to slip it (far easier than a dropdown). */
function FMNode({ data }: NodeProps) {
  const { label, name, state, clickable, faded, kind, isHandover, sub, big } = data as {
    label: string; name: string; state: State; clickable: boolean; faded: boolean;
    kind: Kind; isHandover: boolean; sub?: string; big?: boolean;
  };
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
  // Node types are labelled so a P&D item is never mistaken for a schedule
  // activity at a glance. Activities also show their P6 code, because an
  // anonymised schedule may have its names wiped and the code is what a
  // scheduler searches P6 by.
  const tag = isHandover ? "Handover" : KIND_TAG[kind];
  const code = sub ?? (kind === "activity" && label !== name ? label : "");
  return (
    <div className={`${big ? "w-[184px]" : "w-[172px]"} rounded-xl border px-3 py-1.5 backdrop-blur-sm transition-all duration-300 ${styles[state]} ${clickHint} ${faded ? "opacity-[0.28]" : "opacity-100"}`}>
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-line-strong" />
      <div className={`flex items-center justify-between gap-2 ${big ? "text-[0.62rem]" : "text-[0.55rem]"} font-semibold uppercase tracking-[0.08em] opacity-70`}>
        <span>{tag}</span>
        {code && <span className="truncate font-mono normal-case tracking-normal">{code}</span>}
      </div>
      {/* The name is what a site manager recognises; the database id (MAT-1)
          means nothing to them, so it is kept as the tooltip only. */}
      <div className="flex items-center gap-2" title={label}>
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${active ? "bg-current" : "bg-steel"}`} />
        <span className={`truncate ${big ? "text-[0.82rem]" : "text-[0.72rem]"} font-semibold leading-tight`}>{name}</span>
      </div>
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-line-strong" />
    </div>
  );
}

/* Stands in for the middle of a long traced path. */
function FoldNode({ data }: NodeProps) {
  const { count } = data as { count: number };
  return (
    <div className="w-[184px] rounded-xl border border-dashed border-red/60 bg-red/[0.07] px-3 py-2 text-center text-red">
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-line-strong" />
      <div className="text-[0.82rem] font-semibold">… {count} more activities</div>
      <div className="text-[0.62rem] uppercase tracking-[0.08em] opacity-70">pushed back on this path</div>
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-line-strong" />
    </div>
  );
}

const nodeTypes = { fm: FMNode, fold: FoldNode };
const shortName = (n: string) => n.replace(/\s*\(.*?\)/, "").split(",")[0];

function stateOf(id: string, delayed: Set<string>, slipped: Set<string>,
                 handover: string, handoverBreaks?: boolean): State {
  if (delayed.has(id)) return "delayed";
  if (slipped.has(id)) return "slipped";
  if (id === handover) return handoverBreaks ? "handover-break" : "handover-safe";
  return "dim";
}

/* ---------------------------------------------------------------- full view
   The original layout, unchanged: one column per kind, every node shown, and
   anything off the active cascade faded. */
function fullView(project: Project, delayed: Set<string>, slipped: Set<string>, handoverBreaks?: boolean) {
  const counters: Record<string, number> = { supplier: 0, material: 0, activity: 0 };
  const heights = { supplier: 6, material: 8, activity: 12 };
  const tallest = Math.max(...Object.values(heights));

  // Focus mode: when something is delayed, fade everything not on the
  // active cascade so the eye follows what breaks (declutters the web).
  const focus = delayed.size > 0;
  const involved = new Set<string>([...delayed, ...slipped, project.handover]);
  const near = new Set<string>(involved);
  for (const e of project.edges)
    if (involved.has(e.source) || involved.has(e.target)) { near.add(e.source); near.add(e.target); }

  const nodes: Node[] = project.nodes.map((n) => {
    const kind = n.kind as Kind;
    const i = counters[kind]++;
    const offset = ((tallest - heights[kind]) * GAP) / 2;
    return {
      id: n.id, type: "fm",
      position: { x: COL[kind], y: offset + i * GAP },
      data: { label: n.id, name: shortName(n.name), kind, isHandover: n.id === project.handover,
              state: stateOf(n.id, delayed, slipped, project.handover, handoverBreaks),
              clickable: kind === "material", faded: focus && !near.has(n.id) },
      draggable: false,
    };
  });

  const hot = new Set<string>([...delayed, ...slipped]);
  const edges: Edge[] = project.edges.map((e, i) => {
    const isHot = hot.has(e.source) && (hot.has(e.target) || e.target === project.handover);
    let cls = "fm-dim";
    if (isHot) cls = "fm-hot";
    else if (focus && !(near.has(e.source) && near.has(e.target))) cls = "fm-faint";
    return { id: `e${i}`, source: e.source, target: e.target, type: "default", animated: isHot, className: cls };
  });
  return { nodes, edges, shownActivities: project.counts.activities };
}

/* --------------------------------------------------------------- trace view
   For big schedules: only what the selected items touch. */
function traceView(project: Project, delayed: Set<string>, slipped: Set<string>,
                   handoverBreaks: boolean | undefined, limit: number) {
  const kindOf = new Map(project.nodes.map((n) => [n.id, n.kind as Kind]));
  const nodeById = new Map(project.nodes.map((n) => [n.id, n]));
  const out = new Map<string, string[]>();
  for (const e of project.edges) {
    if (!out.has(e.source)) out.set(e.source, []);
    out.get(e.source)!.push(e.target);
  }
  const H = project.handover;
  const fedOf = (m: string) => (out.get(m) ?? []).filter((f) => kindOf.get(f) === "activity");

  // How much schedule an item pushes back: the pushed-back activities you can
  // reach from where it lands. Decides which items to draw when there are many.
  const reach = (m: string) => {
    const queue = fedOf(m).filter((f) => slipped.has(f));
    const seen = new Set<string>(queue);
    while (queue.length) {
      const cur = queue.shift()!;
      for (const nx of out.get(cur) ?? [])
        if (!seen.has(nx) && slipped.has(nx)) { seen.add(nx); queue.push(nx); }
    }
    return seen.size;
  };
  const all = [...delayed].filter((id) => kindOf.get(id) === "material");
  // P&D items whose Schedule Activity ID matched nothing in P6: they cannot
  // move the handover, and the screen should say so rather than look empty.
  const unlinked = all.filter((m) => fedOf(m).length === 0).map((m) => nodeById.get(m)?.name ?? m);
  const traced = all
    .map((m) => ({ m, r: reach(m) }))
    .sort((a, b) => b.r - a.r || a.m.localeCompare(b.m, undefined, { numeric: true }))
    .slice(0, limit)
    .map((x) => x.m);

  const visible = new Set<string>([H]);
  const synthetic: Edge[] = [];
  const folds: { id: string; count: number }[] = [];

  for (const m of traced) {
    visible.add(m);
    for (const f of fedOf(m)) {
      visible.add(f);
      // Shortest route (in steps) from where the item lands to handover,
      // walking only through activities that were actually pushed back.
      const parent = new Map<string, string>([[f, f]]);
      const queue = [f];
      let reached = false;
      const nearest: string[] = [];
      while (queue.length && !reached) {
        const cur = queue.shift()!;
        for (const nx of out.get(cur) ?? []) {
          if (parent.has(nx) || kindOf.get(nx) !== "activity") continue;
          if (!(slipped.has(nx) || nx === H)) continue;
          parent.set(nx, cur);
          if (nx === H) { reached = true; break; }
          nearest.push(nx);
          queue.push(nx);
        }
      }
      if (reached && handoverBreaks) {
        const path: string[] = [];
        for (let c = H; ; c = parent.get(c)!) { path.push(c); if (c === f) break; }
        path.reverse();
        if (path.length > PATH_HEAD + PATH_TAIL + 1) {
          const head = path.slice(0, PATH_HEAD), tail = path.slice(-PATH_TAIL);
          const fold = { id: `fold:${f}`, count: path.length - PATH_HEAD - PATH_TAIL };
          folds.push(fold);
          head.forEach((n) => visible.add(n)); tail.forEach((n) => visible.add(n));
          synthetic.push({ id: `${fold.id}:in`, source: head[head.length - 1], target: fold.id, type: "default", animated: true, className: "fm-hot" });
          synthetic.push({ id: `${fold.id}:out`, source: fold.id, target: tail[0], type: "default", animated: true, className: "fm-hot" });
        } else {
          path.forEach((n) => visible.add(n));
        }
      } else {
        // Handover holds: show the nearest activities this pushed back before
        // the float absorbed it — that IS the story when nothing breaks.
        nearest.slice(0, SIDE_CAP).forEach((n) => visible.add(n));
      }
    }
  }

  // Real edges among what's shown (skipping ones that jump across a fold,
  // which would draw a misleading shortcut over the folded middle).
  const foldedAway = (s: string, t: string) =>
    folds.some((fd) => synthetic.some((se) => se.target === fd.id && se.source === s) &&
                       synthetic.some((se) => se.source === fd.id && se.target === t));
  const hot = new Set<string>([...delayed, ...slipped]);
  const edges: Edge[] = [];
  project.edges.forEach((e, i) => {
    if (!visible.has(e.source) || !visible.has(e.target) || foldedAway(e.source, e.target)) return;
    if (kindOf.get(e.source) === "supplier") return;   // vendor rides inside the item
    const isHot = hot.has(e.source) && (hot.has(e.target) || e.target === H);
    edges.push({ id: `e${i}`, source: e.source, target: e.target, type: "default",
                 animated: isHot, className: isHot ? "fm-hot" : "fm-dim" });
  });
  edges.push(...synthetic);

  // Columns by dependency depth: each activity sits one column right of its
  // latest visible predecessor, so a path reads left → right to handover.
  const actIds = [...visible].filter((id) => kindOf.get(id) === "activity").concat(folds.map((f) => f.id));
  const actSet = new Set(actIds);
  const preds = new Map<string, string[]>(actIds.map((id) => [id, []]));
  for (const e of edges) if (actSet.has(e.target) && actSet.has(e.source)) preds.get(e.target)!.push(e.source);
  const level = new Map<string, number>();
  const levelOf = (id: string, seen = new Set<string>()): number => {
    if (level.has(id)) return level.get(id)!;
    if (seen.has(id)) return 0;               // never loops on a DAG; guard anyway
    seen.add(id);
    const ps = preds.get(id) ?? [];
    const l = ps.length ? Math.max(...ps.map((p) => levelOf(p, seen))) + 1 : 0;
    level.set(id, l);
    return l;
  };
  actIds.forEach((id) => levelOf(id));
  const maxLevel = Math.max(0, ...actIds.filter((id) => id !== H).map((id) => level.get(id) ?? 0));
  if (actSet.has(H)) level.set(H, maxLevel + 1);     // handover always last

  const columns = new Map<number, string[]>();
  for (const id of actIds) {
    const l = level.get(id) ?? 0;
    if (!columns.has(l)) columns.set(l, []);
    columns.get(l)!.push(id);
  }

  // Rows: items in order of how much they push back; every later column is
  // ordered by the average height of what feeds it, so lines cross less.
  const pos = new Map<string, { x: number; y: number }>();
  const center = (i: number, n: number) => (i - (n - 1) / 2) * T_GAP;
  traced.forEach((id, i) => pos.set(id, { x: 0, y: center(i, traced.length) }));
  const feeders = new Map<string, string[]>();
  for (const e of edges) {
    if (!feeders.has(e.target)) feeders.set(e.target, []);
    feeders.get(e.target)!.push(e.source);
  }
  const avgY = (id: string) => {
    const ys = (feeders.get(id) ?? []).map((p) => pos.get(p)?.y).filter((y): y is number => y !== undefined);
    return ys.length ? ys.reduce((s, y) => s + y, 0) / ys.length : Number.POSITIVE_INFINITY;
  };
  for (const l of [...columns.keys()].sort((a, b) => a - b)) {
    const order = columns.get(l)!.map((id, k) => ({ id, k, y: avgY(id) }))
      .sort((a, b) => (a.y === b.y ? a.k - b.k : a.y - b.y));
    order.forEach(({ id }, i) => pos.set(id, { x: T_ACT_X + l * T_STEP, y: center(i, order.length) }));
  }

  const nodes: Node[] = [...visible].filter((id) => pos.has(id)).map((id) => {
    const n = nodeById.get(id)!;
    const kind = n.kind as Kind;
    return {
      id, type: "fm", position: pos.get(id)!,
      data: { label: id, name: shortName(n.name), kind, isHandover: id === H,
              state: stateOf(id, delayed, slipped, H, handoverBreaks),
              clickable: kind === "material", faded: false,
              sub: kind === "material" ? nodeById.get(n.supplier ?? "")?.name : undefined, big: true },
      draggable: false,
    };
  });
  for (const fd of folds)
    nodes.push({ id: fd.id, type: "fold", position: pos.get(fd.id) ?? { x: 0, y: 0 },
                 data: { count: fd.count }, draggable: false });

  const shownActivities = actIds.length - folds.length;
  return { nodes, edges, shownActivities, items: traced.length, totalItems: all.length, unlinked };
}

export default function GraphCanvas({
  project, delayedIds, slippedIds, handoverBreaks, onToggleMaterial,
}: {
  project: Project; delayedIds?: Set<string>; slippedIds?: Set<string>;
  handoverBreaks?: boolean; onToggleMaterial?: (id: string) => void;
}) {
  const materialIds = useMemo(
    () => new Set(project.nodes.filter((n) => n.kind === "material").map((n) => n.id)),
    [project]);
  const large = project.counts.activities > LARGE_AT;

  // Stable content keys for the two highlight Sets (see the memo below).
  const delayedKey = [...(delayedIds ?? [])].sort().join(",");
  const slippedKey = [...(slippedIds ?? [])].sort().join(",");

  const [showAll, setShowAll] = useState(false);

  const view = useMemo(() => {
    const slipped = slippedIds ?? new Set<string>();
    const delayed = delayedIds ?? new Set<string>();
    return large
      ? traceView(project, delayed, slipped, handoverBreaks,
                  showAll ? Number.POSITIVE_INFINITY : TOP_TRACED)
      : { ...fullView(project, delayed, slipped, handoverBreaks), items: delayed.size,
          totalItems: delayed.size, unlinked: [] as string[] };
    // Keyed on the Sets' CONTENTS, not their object identity: a caller that
    // rebuilds `new Set(...)` inline every render would otherwise invalidate
    // this memo forever, and React Flow silently drops its edges when fed new
    // nodes/edges array identities at that rate. Content keys make the rebuild
    // happen only when something really changed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, delayedKey, slippedKey, handoverBreaks, large, showAll]);
  const { nodes, edges } = view;

  // Belt-and-suspenders against the "blank until resize" React Flow race:
  // keep the instance and re-fit whenever the container actually resizes.
  const wrapRef = useRef<HTMLDivElement>(null);
  const rf = useRef<ReactFlowInstance | null>(null);

  // THE BLANK-GRAPH FIX. React Flow resolves each edge against its source and
  // target in its internal node store, and if an edge arrives before those
  // nodes are registered it is dropped — permanently, with no retry and no
  // error. So edges are only handed over one frame AFTER the node set they
  // refer to. This used to run once at mount; trace mode brings in a new node
  // set on every selection, so the guard is keyed on WHICH nodes are showing.
  const nodeKey = useMemo(() => nodes.map((n) => n.id).join("|"), [nodes]);
  const nodeKeyRef = useRef(nodeKey);
  nodeKeyRef.current = nodeKey;
  const [readyKey, setReadyKey] = useState<string | null>(null);
  useEffect(() => {
    if (!rf.current) return;               // first mount is handled by onInit
    const a = requestAnimationFrame(() => {
      setReadyKey(nodeKey);
      requestAnimationFrame(() => rf.current?.fitView({ padding: 0.12, duration: 300 }));
    });
    return () => cancelAnimationFrame(a);
  }, [nodeKey]);
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => rf.current?.fitView({ padding: 0.12 }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const headers = large
    ? [view.totalItems > view.items
         ? `Tracing ${view.items} of ${view.totalItems} P&D items`
         : `Tracing ${view.items} P&D item${view.items === 1 ? "" : "s"}`,
       `showing ${view.shownActivities} of ${project.counts.activities.toLocaleString()} activities`]
    : ["Suppliers", "P&D items", "Schedule activities → Handover"];

  return (
    <div ref={wrapRef} className="relative h-[68vh] min-h-[560px] w-full overflow-hidden rounded-2xl border border-line bg-black/40">
      <div className="pointer-events-none absolute inset-0 z-[1]"
        style={{ background: "radial-gradient(ellipse 60% 55% at 55% 45%, rgba(245,166,35,0.06), transparent 65%)" }} />
      <div className="pointer-events-none absolute inset-0 z-[1]"
        style={{ boxShadow: "inset 0 0 160px 40px rgba(0,0,0,0.75)" }} />
      <ReactFlow
        nodes={nodes} edges={readyKey === nodeKey ? edges : []} nodeTypes={nodeTypes}
        fitView fitViewOptions={{ padding: 0.12 }}
        nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
        onNodeClick={(_, node) => { if (materialIds.has(node.id)) onToggleMaterial?.(node.id); }}
        // Nodes are registered by the time onInit fires — release the edges on
        // the next frame (see the readyKey comment above), and re-fit once
        // the container has actually painted.
        onInit={(inst) => {
          rf.current = inst;
          requestAnimationFrame(() => setReadyKey(nodeKeyRef.current));
          setTimeout(() => inst.fitView({ padding: 0.12 }), 60);
        }}
        proOptions={{ hideAttribution: true }} minZoom={large ? 0.05 : 0.2} maxZoom={1.4}>
        <Background variant={BackgroundVariant.Dots} gap={26} size={1} color="rgba(255,255,255,0.05)" />
        <Panel position="top-left" className="!m-4 flex flex-col gap-2">
          <div className="flex gap-2">
            {headers.map((l) => (
              <span key={l} className="kicker rounded-md border border-line bg-elev/70 px-2.5 py-1 backdrop-blur">{l}</span>
            ))}
            {large && view.totalItems > TOP_TRACED && (
              <button type="button" onClick={() => setShowAll((v) => !v)}
                className="kicker rounded-md border border-amber/50 bg-amber/10 px-2.5 py-1 !text-amber backdrop-blur transition-colors hover:bg-amber/20">
                {showAll ? `Show top ${TOP_TRACED}` : `Show all ${view.totalItems}`}
              </button>
            )}
          </div>
          <span className="kicker !text-amber/80">
            {!large ? "↳ click materials to slip several at once"
              : view.totalItems > view.items
                ? `↳ showing the ${view.items} that push back the most work — "Show all" draws every one`
                : view.items > TOP_TRACED
                  ? "↳ every item traced — scroll to zoom in, drag to move around"
                  : "↳ large schedule — add P&D items on the left to trace their path to handover"}
          </span>
        </Panel>
        {large && view.items === 0 && (
          <Panel position="top-center" className="!mt-24 rounded-xl border border-line bg-elev/80 px-5 py-4 text-center backdrop-blur">
            <div className="text-sm font-semibold">Pick a P&amp;D item to trace</div>
            <div className="mt-1 text-xs text-muted">
              {project.counts.activities.toLocaleString()} activities is too many to draw at once — Foreman shows the path from the items you slip to handover.
            </div>
          </Panel>
        )}
        {view.unlinked.length > 0 && (
          <Panel position="bottom-left" className="!m-4 max-w-sm rounded-xl border border-amber/40 bg-elev/85 px-4 py-3 backdrop-blur">
            <div className="text-xs font-semibold text-amber">
              Not linked to the schedule: {view.unlinked.map(shortName).join(", ")}
            </div>
            <div className="mt-1 text-[0.7rem] text-muted">
              Its Schedule Activity ID matched no P6 activity, so it can't move the handover. Check the ID in the P&amp;D log.
            </div>
          </Panel>
        )}
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
