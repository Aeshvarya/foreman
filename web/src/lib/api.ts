// Typed client for the Foreman API (backend/main.py). Vite proxies /api → :8000.

export type NodeKind = "supplier" | "material" | "activity";

export interface GraphNode {
  id: string;
  kind: NodeKind;
  name: string;
  confidence?: number | null;
  shipment_status?: string | null;
  supplier?: string | null;
  needs_materials?: string[] | null;
  depends_on?: string[] | null;
}
export interface GraphEdge { source: string; target: string; kind: string; }
export interface Project {
  name: string;
  handover: string;
  counts: { suppliers: number; materials: number; activities: number; edges: number };
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Material { id: string; name: string; supplier: string; confidence: number; }

export interface CascadeSlip {
  activity: string; name: string;
  baseline_finish: string; new_finish: string; slip_days: number;
}
export interface CascadeReport {
  delayed_material: string; delay_days: number;
  slipped: CascadeSlip[]; absorbed: CascadeSlip[];
  handover_slip_days: number; handover_date: string; baseline_handover: string;
  confidence: number; confidence_source: string; mitigation: string;
}

export interface RiskItem {
  material_id: string; name: string; supplier: string;
  breaking_point_days: number | null; confidence: number;
  confidence_source: string; risk_score: number; verdict: string;
}

export interface MonteCarlo {
  n: number; p_slip: number; mean_slip: number; p50_slip: number; p90_slip: number;
  baseline_handover: string;
  drivers: { material: string; name: string; risk_contribution: number }[];
}

export interface AltSupplier {
  material: string; name: string; category: string | null; days_to_roj: number | null;
  alternates: {
    id: string; name: string; region: string; reliability: number;
    lead_days: number; fit: number; meets_roj: boolean; note?: string;
  }[];
}

export interface TraceStep { step: string; detail: string; }
export interface AskResult {
  answer: string; citations: string[]; trace: TraceStep[]; mode: "query" | "cascade" | "scene";
}

/** Snapshot of the live Cascade Simulator state, sent to /api/ask so the
 * assistant can explain what's currently on screen instead of re-querying
 * the static graph. Written by the Cascade tool, read by any Ask surface. */
export interface CascadeScene {
  delayed: { id: string; name: string; days: number }[];
  handover_breaks: boolean;
  handover_slip_days: number;
  baseline_handover: string;
  new_handover: string;
  confidence: number;
  slipped_activities: { id: string; name: string; slip_days: number }[];
  absorbed_by_float: string[];
  mitigation: string;
}

/** The morning brief — the project read on the user's behalf and phrased as
 * sentences, so the home page never demands that they know what to ask. */
export interface BriefItem {
  id: string; name: string; supplier: string;
  status: "needs you today" | "worth a call" | "keep an eye on it" | "fine";
  weight: number;
  slack_days: number | null; slack_text: string;
  how_sure: string; confidence: number; based_on: string;
  risk_text: string;
  week_slip_days: number; week_slip_cost: number; week_slip_cost_label: string;
  action: string;
}
export interface Brief {
  project: string; handover: string | null;
  headline: string; tone: "urgent" | "watch" | "calm"; subhead: string;
  at_stake: number; at_stake_label: string;
  counts: { urgent: number; watch: number; total: number };
  items: BriefItem[];
}

/** The rupee layer. Every amount arrives with a `formula` string and a
 * `source` of "your number" | "assumed", so the UI can always show where a
 * figure came from instead of asking anyone to trust it. */
export interface MoneySetting {
  key: string; value: number; source: "your number" | "assumed";
  label: string; plain: string; basis: string;
}
export type MoneySettings = Record<string, MoneySetting>;

export interface CostLine {
  key: string; label: string; plain: string;
  amount: number; formula: string; source: string; basis: string;
}
export interface CostOfDelay {
  slip_days: number; currency: string;
  total: number; total_label: string;
  per_day: number; per_day_label: string;
  lines: CostLine[]; assumed: boolean;
}

export interface RecoveryOption {
  id: string; kind: "expedite" | "switch" | "overtime" | "none";
  material?: string; activity?: string;
  title: string; plain: string;
  days_saved: number;
  cost: number; cost_label: string;
  avoided?: number; exposure_after?: number;
  net: number; net_label: string;
  feasible: boolean; confidence: string;
  how: string[]; why: string;
}
export interface RecoveryPlan {
  handover_slip_days: number;
  exposure: CostOfDelay;
  options: RecoveryOption[];
  do_nothing: RecoveryOption;
  best: RecoveryOption | null;
}

export interface BuildResult {
  docs: number; facts: number;
  materials: Record<string, {
    confidence: number; confidence_source: string; conflict: boolean;
    attributes: Record<string, { value: string; confidence: number; source_type: string; source_doc: string }>;
  }>;
  conflicts: {
    material: string; attribute: string; confidence: number;
    kept: { value: string; source: string; doc: string };
    rejected: { value: string; source: string; doc: string }[];
  }[];
  trace: TraceStep[];
}

export interface DocFile { name: string; seed: boolean; size: number; }

export interface ProjectMeta { id: string; name: string; created: string; active: boolean; seed?: boolean; }

// Payload the New Project builder sends (ids pre-assigned by order).
export interface NewProjectInput {
  project: { name: string; start_date: string; handover_milestone?: string };
  suppliers: { id: string; name: string; region?: string; reliability?: number }[];
  materials: { id: string; name: string; supplier: string; expected_arrival: string; roj_date: string; confidence: number }[];
  activities: { id: string; name: string; duration_days: number; needs_materials: string[]; depends_on: string[] }[];
}

/** A project understood from a sentence or a spreadsheet, held for the user to
 * confirm. Nothing is saved until they do. */
export interface ProjectDraft {
  draft: NewProjectInput & { project: { name: string; start_date: string; handover_milestone: string } };
  summary: string;
  warnings: string[];
  counts: { suppliers: number; materials: number; activities: number };
  extracted?: string;
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}
async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `${path} → ${r.status}`);
  return r.json();
}
async function del<T>(path: string): Promise<T> {
  const r = await fetch(path, { method: "DELETE" });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

export const api = {
  project: () => get<Project>("/api/project"),
  materials: () => get<Material[]>("/api/materials"),
  cascade: (material_id: string, delay_days: number) =>
    post<CascadeReport>("/api/cascade", { material_id, delay_days }),
  cascadeMulti: (delays: Record<string, number>) =>
    post<CascadeReport>("/api/cascade-multi", { delays }),
  risk: () => get<RiskItem[]>("/api/risk"),
  montecarlo: () => get<MonteCarlo>("/api/montecarlo"),
  altSupplier: (id: string) => get<AltSupplier>(`/api/alt-supplier/${id}`),
  ask: (question: string, scene?: CascadeScene) =>
    post<AskResult>("/api/ask", scene ? { question, scene } : { question }),
  today: () => get<Brief>("/api/today"),
  money: () => get<MoneySettings>("/api/money"),
  saveMoney: async (patch: Record<string, number | null>) => {
    const r = await fetch("/api/money", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `money → ${r.status}`);
    return r.json() as Promise<MoneySettings>;
  },
  costOfDelay: (slip_days: number) => post<CostOfDelay>("/api/cost-of-delay", { slip_days }),
  recovery: (delays: Record<string, number>) => post<RecoveryPlan>("/api/recovery", { delays }),
  buildGraph: () => post<BuildResult>("/api/build-graph", {}),
  docs: () => get<DocFile[]>("/api/docs"),
  uploadDocs: async (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    const r = await fetch("/api/docs/upload", { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `upload → ${r.status}`);
    return r.json() as Promise<{ saved: string[]; docs: DocFile[] }>;
  },
  resetDocs: () => post<{ removed: number; docs: DocFile[] }>("/api/docs/reset", {}),
  projects: () => get<ProjectMeta[]>("/api/projects"),
  createProject: (data: NewProjectInput) => post<{ id: string }>("/api/projects", data),
  draftProject: (text: string) => post<ProjectDraft>("/api/projects/draft", { text }),
  draftProjectFromFile: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch("/api/projects/draft-file", { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `import → ${r.status}`);
    return r.json() as Promise<ProjectDraft>;
  },
  activateProject: (id: string) => post<{ active: string }>(`/api/projects/${id}/activate`, {}),
  deleteProject: (id: string) => del<{ active: string }>(`/api/projects/${id}`),
};
