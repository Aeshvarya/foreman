# Foreman — API Reference

FastAPI, defined in `backend/main.py`. 27 endpoints. The same app serves the
built SPA as a catch-all route, so the API and frontend share an origin in
deployment.

> 🔴 **No endpoint requires authentication.** Read *and* write paths are open to
> anyone with the URL. See the Security section at the bottom before exposing
> this anywhere real.

Base URL (hosted demo): `https://foreman-yi3t.onrender.com`
Base URL (local): `http://localhost:8000`

## Request models

```python
CascadeReq       { material_id: str, delay_days: int = 5 }
CascadeMultiReq  { delays: dict[str, int] }        # {material_id: delay_days}
AskReq           { question: str, scene: dict | None }
```

---

## Health & project

### `GET /api/health`
Liveness plus what the instance is actually running on — a deployment degrades
quietly (same pages, worse answers), so this reports which graph store answered.
Returns booleans and a store name, never a URI or key.

```json
{ "ok": true, "graph": "neo4j", "graph_detail": "26 nodes", "llm": true }
```

`graph` is `"neo4j"` or `"json"`. If Neo4j is configured but unreachable,
`graph_detail` carries the reason.

### `GET /api/project`
Graph summary plus nodes and edges for the visualisation.

```json
{ "name": "...", "handover": "2026-11-04", "demo": true,
  "counts": { "suppliers": 6, "materials": 8, "activities": 12, "edges": 29 },
  "nodes": [{ "id", "kind", "name", "confidence", "shipment_status",
              "supplier", "needs_materials", "depends_on" }],
  "edges": [{ "source", "target", "kind" }] }
```

`demo: true` means the active project is the bundled synthetic one. The UI uses
this to label demo data as synthetic on screen — an honesty claim only counts if
it's visible in the app, not just the README.

### `GET /api/materials`
`[{ id, name, supplier, confidence }]`

---

## Cascade (the core)

### `POST /api/cascade`
Body: `CascadeReq`. Propagates one material's delay through the CPM schedule.
Returns a serialised `CascadeReport`: which activities move, how much float
absorbs, whether the handover breaks and by how many days.

`400` if `material_id` is not a material node.

### `POST /api/cascade-multi`
Body: `CascadeMultiReq`. Combined cascade over several simultaneous delays.

---

## Risk

### `GET /api/risk`
The risk radar: every material with its breaking point (days it can slip before
handover breaks) and confidence. Low + low = silent killer.

### `GET /api/montecarlo`
Runs the Monte Carlo simulation (default 3000 iterations, seed 7). Returns
P(slip), slip distribution (mean / P50 / P90), and per-material risk
contribution. Same-supplier materials are correlated, not independent.

### `GET /api/alt-supplier/{material_id}`
Ranked alternate suppliers in the same category, scored on reliability, lead
time and region proximity, and filtered by whether their lead time still fits
the days remaining.

### `GET /api/today`
The morning brief — ranked, plain-language sentences about what needs attention
today.

---

## Money

### `GET /api/currency` — active currency and rate info
### `GET /api/money` — current commercial settings
### `PUT /api/money` — patch commercial settings (validated by `money.clean_patch`)
### `POST /api/cost-of-delay` — cash cost of a given slip

Every returned line carries `source` (`"your number"` / `"assumed"`), a `basis`
sentence, and a `formula` string showing its arithmetic.

### `POST /api/cost-of-waiting`
The time machine: what a week of doing nothing costs, with checkpoints showing
recovery options expiring over time.

---

## Recovery & comms

### `POST /api/recovery`
Body: `CascadeMultiReq`. Ranked recovery options — expedite, switch supplier,
overtime — each with days bought, cost and net saving. Always includes
"do nothing" with its own cost.

### `POST /api/messages`
Body: `CascadeMultiReq`. Drafts the supplier message, the client message and a
one-pager.

---

## Agents

### `POST /api/ask`
Body: `AskReq`. Routes through `agents.brain`: delay what-ifs go to the cascade
agent (grounded CPM math), everything else to the NL→Cypher query agent.

```json
{ "answer": "...", "citations": [...], "trace": [...], "mode": "cascade|query" }
```

Pass `scene` to ask about the live on-screen Cascade Simulator state.

---

## Documents → graph

### `GET /api/docs` — list ingested documents
### `POST /api/docs/upload` 🔴 *write* — multipart upload; `python-multipart` required
### `POST /api/docs/reset` 🔴 *write* — clear the document set
### `POST /api/build-graph` 🔴 *write* — run the KG builder over the documents and write to Neo4j

Extract → score by source → verify (resolve conflicts by source weight) →
construct. Every resulting material status carries a confidence and a source.

---

## Projects

### `GET /api/projects` — list, with which is active
### `POST /api/projects` 🔴 *write* — create from structured data
### `POST /api/projects/draft` 🔴 *write* — build a project draft from a sentence
### `POST /api/projects/draft-file` 🔴 *write* — build a draft from an uploaded spreadsheet (.xlsx)
### `POST /api/projects/{pid}/activate` 🔴 *write* — set active; reloads Neo4j
### `DELETE /api/projects/{pid}` 🔴 *destructive* — delete a project

---

## Startup behaviour

On boot (`_startup`) the app loads the active project into Neo4j with up to 8
retries (`_load_active_into_neo4j`) and warms the LLM (`_warm_llm`). Cold starts
on the free Render tier can take a while — worth knowing before a live demo.

## CORS

`ALLOWED_ORIGINS`, default `http://localhost:5173,http://127.0.0.1:5173`.

---

## 🔴 Security

**No authentication on any endpoint.** In particular these are open to anyone
who has the URL:

```
POST   /api/projects
POST   /api/projects/draft
POST   /api/projects/draft-file
POST   /api/docs/upload
POST   /api/docs/reset
POST   /api/build-graph
PUT    /api/money
DELETE /api/projects/{pid}      ← destructive
```

This was acceptable for a hackathon deployment on synthetic data. It is a
blocker for anything touching client data, and it is the reason real project
data must stay off the hosted instance until auth exists.

Adding auth is scoped as part of the architecture landing spike, not demo week.
