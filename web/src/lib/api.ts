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
  answer: string; citations: string[]; trace: TraceStep[]; mode: "query" | "cascade";
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

export interface ProjectMeta { id: string; name: string; created: string; active: boolean; seed?: boolean; }

// Payload the New Project builder sends (ids pre-assigned by order).
export interface NewProjectInput {
  project: { name: string; start_date: string; handover_milestone?: string };
  suppliers: { id: string; name: string; region?: string; reliability?: number }[];
  materials: { id: string; name: string; supplier: string; expected_arrival: string; roj_date: string; confidence: number }[];
  activities: { id: string; name: string; duration_days: number; needs_materials: string[]; depends_on: string[] }[];
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
  ask: (question: string) => post<AskResult>("/api/ask", { question }),
  buildGraph: () => post<BuildResult>("/api/build-graph", {}),
  projects: () => get<ProjectMeta[]>("/api/projects"),
  createProject: (data: NewProjectInput) => post<{ id: string }>("/api/projects", data),
  activateProject: (id: string) => post<{ active: string }>(`/api/projects/${id}/activate`, {}),
  deleteProject: (id: string) => del<{ active: string }>(`/api/projects/${id}`),
};
