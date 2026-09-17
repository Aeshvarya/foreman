import { useMemo, useRef, useEffect, useState } from "react";
import {
  ReactFlow, Background, BackgroundVariant, Handle, Position, Panel,
  Controls,
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
const T_GAP = 104, T_STEP = 268, T_ACT_X = 300;
/* When the handover holds, how many absorbed-but-pushed-back activities to show
   downstream of each item before stopping. */
const SIDE_CAP = 8;
/* A run of activities with one way in and one way out says nothing beyond "and
   then N more jobs", but it costs a column each. On a real schedule those runs
   stretched the drawing to ~3,000px wide, and fitting that into the canvas put
   every label at about 5px. Runs this long or longer collapse into one node. */
const CHAIN_MIN = 3;
/* Below this zoom the labels stop being words: at the 0.42x a real schedule
   used to fit at, a 0.82rem name renders about 5px tall. The view fits the
   drawing when it can, and when it cannot it opens at this zoom on the
   left-hand items and lets the user pan, rather than showing an unreadable
   whole — the minimap says how much more there is. */
const MIN_READABLE = 0.62;

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
  // The code is here so a scheduler can find the row in P6 ("A1520"). An
  // anonymised export puts a 32-character hash in that field instead, which
  // searches nothing and eats the whole header line, so it is left off. Same
  // for a supplier line that just repeats the item's own name.
  const p6code = kind === "activity" && label !== name
    && label.length <= 16 && !/[0-9a-f]{12}/i.test(label) ? label : "";
  const vendor = sub && !sub.toLowerCase().includes(name.toLowerCase()) ? sub : "";
  const code = sub !== undefined ? vendor : p6code;
  return (
    <div className={`${big ? "w-[208px]" : "w-[172px]"} rounded-xl border px-3 py-1.5 backdrop-blur-sm transition-all duration-300 ${styles[state]} ${clickHint} ${faded ? "opacity-[0.28]" : "opacity-100"}`}>
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-line-strong" />
      <div className={`flex items-center justify-between gap-2 ${big ? "text-[0.62rem]" : "text-[0.55rem]"} font-semibold uppercase tracking-[0.08em] opacity-70`}>
        <span>{tag}</span>
        {code && <span className="truncate font-mono normal-case tracking-normal">{code}</span>}
      </div>
      {/* The name is what a site manager recognises; the database id (MAT-1)
          means nothing to them, so it is kept as the tooltip only. */}
      <div className="flex items-center gap-2" title={label}>
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${active ? "bg-current" : "bg-steel"}`} />
        <span className={`truncate ${big ? "text-[0.95rem]" : "text-[0.72rem]"} font-semibold leading-tight`}>{name}</span>
      </div>
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-line-strong" />
    </div>
  );
}

/* Stands in for the middle of a long traced path. */
function FoldNode({ data }: NodeProps) {
  const { count, sub } = data as { count: number; sub?: string };
  return (
    <div className="w-[208px] rounded-xl border border-dashed border-steel/60 bg-steel/[0.07] px-3 py-2 text-center text-steel-bright">
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-line-strong" />
      <div className="text-[0.82rem] font-semibold">… {count} more activities</div>
      <div className="text-[0.62rem] uppercase tracking-[0.08em] opacity-70">{sub ?? "pushed back on this path"}</div>
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
  // Column heights are counted from the project, not hard-coded. They used to be
  // the bundled demo's own 6 / 8 / 12, so any other project centred its columns
  // against the wrong totals and the three stacks sat visibly off each other.
  const heights: Record<Kind, number> = { supplier: 0, material: 0, activity: 0 };
  for (const n of project.nodes) heights[n.kind as Kind] = (heights[n.kind as Kind] ?? 0) + 1;
  const tallest = Math.max(1, ...Object.values(heights));

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
  const folds: { id: string; count: number; sub?: string }[] = [];

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
          synthetic.push({ id: `${fold.id}:in`, source: head[head.length - 1], target: fold.id, type: "smoothstep", animated: true, className: "fm-hot" });
          synthetic.push({ id: `${fold.id}:out`, source: fold.id, target: tail[0], type: "smoothstep", animated: true, className: "fm-hot" });
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
    edges.push({ id: `e${i}`, source: e.source, target: e.target, type: "smoothstep",
                 animated: isHot, className: isHot ? "fm-hot" : "fm-dim" });
  });
  edges.push(...synthetic);

  // ------------------------------------------------- compact linear runs
  // Every step of a straight run costs a column, and the columns are what set
  // the drawing's width, and the width is what fitView divides the canvas by.
  // A run of activities with exactly one way in and one way out carries no
  // branching to look at, so it folds into a single node and gives the rest of
  // the picture its zoom back.
  {
    const inOf = new Map<string, string[]>(), outOf = new Map<string, string[]>();
    for (const e of edges) {
      if (!inOf.has(e.target)) inOf.set(e.target, []);
      if (!outOf.has(e.source)) outOf.set(e.source, []);
      inOf.get(e.target)!.push(e.source);
      outOf.get(e.source)!.push(e.target);
    }
    const plain = (id: string) =>
      kindOf.get(id) === "activity" && id !== H && !traced.includes(id) &&
      (inOf.get(id)?.length ?? 0) === 1 && (outOf.get(id)?.length ?? 0) === 1;
    const done = new Set<string>();
    for (const start of [...visible]) {
      if (!plain(start) || done.has(start)) continue;
      // only start a run at its head, so each run is found once
      const before = inOf.get(start)![0];
      if (plain(before)) continue;
      const run = [start];
      for (let cur = outOf.get(start)![0]; plain(cur) && !done.has(cur); cur = outOf.get(cur)![0])
        run.push(cur);
      if (run.length < CHAIN_MIN) continue;
      run.forEach((id) => done.add(id));
      const head = inOf.get(run[0])![0], tail = outOf.get(run[run.length - 1])![0];
      const fold = { id: `run:${run[0]}`, count: run.length, sub: "in a row, nothing branches off" };
      folds.push(fold);
      run.forEach((id) => visible.delete(id));
      const keep = edges.filter((e) => !run.includes(e.source) && !run.includes(e.target));
      const hotRun = run.some((id) => slipped.has(id));
      keep.push({ id: `${fold.id}:in`, source: head, target: fold.id, type: "smoothstep",
                  animated: hotRun, className: hotRun ? "fm-hot" : "fm-dim" });
      keep.push({ id: `${fold.id}:out`, source: fold.id, target: tail, type: "smoothstep",
                  animated: hotRun, className: hotRun ? "fm-hot" : "fm-dim" });
      edges.length = 0; edges.push(...keep);
    }
  }

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

  // Rows: items in order of how much they push back, then each column ordered by
  // the average row of what it connects to. One forward pass only ever tidies a
  // column against the column on its left, which still left long lines crossing
  // the middle of the drawing; sweeping forward and back a few times settles it
  // (the standard barycentre method), and the crossings drop a lot.
  const pos = new Map<string, { x: number; y: number }>();
  const center = (i: number, n: number) => (i - (n - 1) / 2) * T_GAP;
  const row = new Map<string, number>();
  traced.forEach((id, i) => { pos.set(id, { x: 0, y: center(i, traced.length) }); row.set(id, i); });

  const feeders = new Map<string, string[]>(), followers = new Map<string, string[]>();
  for (const e of edges) {
    if (!feeders.has(e.target)) feeders.set(e.target, []);
    if (!followers.has(e.source)) followers.set(e.source, []);
    feeders.get(e.target)!.push(e.source);
    followers.get(e.source)!.push(e.target);
  }
  const levels = [...columns.keys()].sort((a, b) => a - b);
  // seed: whatever order the column came in
  for (const l of levels) columns.get(l)!.forEach((id, i) => row.set(id, i));

  const bary = (id: string, side: Map<string, string[]>) => {
    const rs = (side.get(id) ?? []).map((n) => row.get(n)).filter((r): r is number => r !== undefined);
    return rs.length ? rs.reduce((a, b) => a + b, 0) / rs.length : Number.POSITIVE_INFINITY;
  };
  const sweep = (order: number[], side: Map<string, string[]>) => {
    for (const l of order) {
      const col = columns.get(l)!;
      const keyed = col.map((id, k) => ({ id, k, b: bary(id, side) }));
      keyed.sort((a, b) => (a.b === b.b ? a.k - b.k : a.b - b.b));
      columns.set(l, keyed.map((x) => x.id));
      keyed.forEach((x, i) => row.set(x.id, i));
    }
  };
  for (let pass = 0; pass < 4; pass++) {
    sweep(levels, feeders);
    sweep([...levels].reverse(), followers);
  }
  sweep(levels, feeders);        // finish facing forward, so column 0 leads

  for (const l of levels) {
    const col = columns.get(l)!;
    col.forEach((id, i) => pos.set(id, { x: T_ACT_X + l * T_STEP, y: center(i, col.length) }));
  }

  // Paint order is array order, and a dim edge drawn last sits on top of the
  // very path the screen is about. Hot edges go last so they read as the story.
  edges.sort((a, b) => Number(a.className === "fm-hot") - Number(b.className === "fm-hot"));

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
                 data: { count: fd.count, sub: fd.sub }, draggable: false });

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

  /* Fitting a real schedule into the canvas used to settle at about 0.42× —
     184px nodes drawn 77px wide, with 5px text. Nobody can read that, and a
     picture nobody can read is worse than a picture of part of it. So the fit
     stops at a legible zoom, and when the drawing is wider than that allows,
     the view opens on the left-hand items (where the traced story starts) and
     the minimap and scroll do the rest. */
  const fitReadable = (duration = 300) => {
    const inst = rf.current, wrap = wrapRef.current;
    if (!inst || !wrap) return;
    const ns = inst.getNodes();
    if (!ns.length) return;
    // The frame is worked out here rather than read back from fitView: fitView
    // applies through a store update, so the zoom it settled on is not
    // readable on the next line, and a correction based on that stale value
    // silently did nothing.
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const n of ns) {
      const w = n.measured?.width ?? n.width ?? 208;
      const h = n.measured?.height ?? n.height ?? 60;
      x0 = Math.min(x0, n.position.x); y0 = Math.min(y0, n.position.y);
      x1 = Math.max(x1, n.position.x + w); y1 = Math.max(y1, n.position.y + h);
    }
    // Asymmetric: the header chips sit over the top-left of the canvas and the
    // zoom buttons over the bottom-right, and the drawing used to start
    // underneath both of them.
    const PAD_T = 92, PAD_X = 28, PAD_B = 28;
    const cw = wrap.clientWidth - 2 * PAD_X, ch = wrap.clientHeight - PAD_T - PAD_B;
    const fit = Math.min(cw / (x1 - x0 || 1), ch / (y1 - y0 || 1), 1);
    const z = Math.max(fit, MIN_READABLE);
    // Fits at a readable size: centre it. Does not: open on the left, where the
    // items being traced are, and let the zoom controls and the scroll wheel do
    // the rest. A picture of part of the schedule beats an unreadable whole.
    setCropped(fit < MIN_READABLE);
    const x = fit >= MIN_READABLE ? PAD_X + (cw - (x1 - x0) * z) / 2 - x0 * z : PAD_X - x0 * z;
    const drawnH = (y1 - y0) * z;
    const y = drawnH <= ch ? PAD_T + (ch - drawnH) / 2 - y0 * z : PAD_T - y0 * z;
    inst.setViewport({ x, y, zoom: z }, { duration });
  };

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
  /* True when the drawing is bigger than a readable zoom can show, so the
     caption can say there is more off-screen instead of letting the view look
     like the whole answer. */
  const [cropped, setCropped] = useState(false);
  useEffect(() => {
    if (!rf.current) return;               // first mount is handled by onInit
    const a = requestAnimationFrame(() => {
      setReadyKey(nodeKey);
      requestAnimationFrame(() => fitReadable());
    });
    return () => cancelAnimationFrame(a);
  }, [nodeKey]);
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => fitReadable(0));
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
        /* No `fitView` prop: React Flow's own fit runs again after the node set
           changes and was overwriting the readable-zoom framing a moment later,
           so the view landed centred on a graph it had just been told not to
           centre. onInit / the nodeKey effect / the resize observer all call
           fitReadable, which is the only thing that should move the view. */
        nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
        onNodeClick={(_, node) => { if (materialIds.has(node.id)) onToggleMaterial?.(node.id); }}
        // Nodes are registered by the time onInit fires — release the edges on
        // the next frame (see the readyKey comment above), and re-fit once
        // the container has actually painted.
        onInit={(inst) => {
          rf.current = inst;
          requestAnimationFrame(() => setReadyKey(nodeKeyRef.current));
          setTimeout(() => fitReadable(0), 60);
        }}
        proOptions={{ hideAttribution: true }} minZoom={large ? 0.05 : 0.2} maxZoom={1.4}>
        <Background variant={BackgroundVariant.Dots} gap={26} size={1} color="rgba(255,255,255,0.05)" />
        {/* Once the view stops trying to show everything at once, there has to be
            a way to know where you are and to get back. Only on the big
            schedules — the 12-node demo needs neither. */}
        {large && (
          <Controls showInteractive={false} position="bottom-right"
            className="!border !border-line !bg-elev/80 !shadow-none [&>button]:!border-line [&>button]:!bg-transparent [&>button]:!fill-muted hover:[&>button]:!bg-surface" />
        )}
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
                : view.items > 0
                  ? "↳ every item traced"
                  : "↳ large schedule — add P&D items on the left to trace their path to handover"}
            {large && cropped && view.items > 0 &&
              " · too big to show at a readable size — drag to move around, scroll to zoom out"}
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
          <Panel position="bottom-center" className="!m-4 max-w-sm rounded-xl border border-amber/40 bg-elev/85 px-4 py-3 backdrop-blur">
            <div className="text-xs font-semibold text-amber">
              Not linked to the schedule: {view.unlinked.map(shortName).join(", ")}
            </div>
            <div className="mt-1 text-[0.7rem] text-muted">
              Its Schedule Activity ID matched no P6 activity, so it can't move the handover. Check the ID in the P&amp;D log.
            </div>
          </Panel>
        )}
        <Panel position="top-right" className="!m-4 flex flex-wrap gap-3 rounded-lg border border-line bg-elev/70 px-3 py-2 backdrop-blur">
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
