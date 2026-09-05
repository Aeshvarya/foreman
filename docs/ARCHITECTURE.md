# Foreman — Architecture

> **Document set:** [`MODULES.md`](MODULES.md) (module-by-module implementation
> detail) · [`DATA-MODEL.md`](DATA-MODEL.md) (graph schema) ·
> [`API.md`](API.md) (all 27 endpoints) · [`SETUP.md`](SETUP.md) (local run) ·
> [`RISK-RADAR.md`](RISK-RADAR.md) (**the named integration target**) ·
> [`LIMITATIONS.md`](LIMITATIONS.md) (**read this one**) ·
> [`NUMBERS.md`](NUMBERS.md) (every published figure, generated from the live
> deployment)

Foreman is a reasoning system for construction supply chains. It doesn't just flag that a
material is late — it computes **what a delay breaks**: which downstream activities slip,
whether the project handover survives, how confident it is, and the cheapest mitigation.
Every schedule number is produced by deterministic Critical-Path-Method math; the language
model only explains it.

## System overview

Three cleanly separated layers. The intelligence is pure Python and knows nothing about the
web; the API exposes it; the frontend consumes it.

```
  Frontend (React + TS + Vite + Tailwind + React Flow)      :5173
      │  HTTP  (fetch /api/*)
  API layer (FastAPI)                                        :8000
      │  Python calls
  Reasoning brain (src/, src/agents/)
      ├─ Neo4j (graph database, source of truth)     ── Docker
      ├─ NetworkX mirror (in-memory, runs the CPM math)
      └─ Gemini (LLM, free tier) for the agents
```

## The reasoning brain (`src/`, `src/agents/`)

| Module | Responsibility |
|---|---|
| `graph.py` | Builds the typed supply-chain graph: `Supplier —SUPPLIES→ Material —FEEDS_ACTIVITY→ Activity —DEPENDS_ON→ … → Handover`, with a confidence score on every edge. |
| `db.py` | Neo4j is the source of truth + the surface the NL agent queries; a NetworkX mirror rebuilt from it runs the CPM math. `tests/test_mirror.py` proves the two are identical. |
| `cascade.py` | The CPM engine. A forward pass honours dependency **and** material-arrival constraints; running it baseline-vs-delayed and diffing yields exactly which activities slip and whether the handover moves. |
| `risk.py` | Binary-searches the cascade engine for each material's **breaking point** and crosses it with confidence to rank the "silent killers". |
| `montecarlo.py` | Models each material's arrival as a distribution whose spread scales with uncertainty, runs 3,000 futures through the CPM engine, and reports P(handover slips) + the dominant driver. |
| `money.py` | Turns schedule slip into cash. **Computes in USD**; every line carries `source` ("your number" / "assumed"), a `basis` sentence and a `formula` string, so a stranger can re-derive the total on paper. INR is a display conversion at a fixed, date-stamped rate. |
| `alt_supplier.py` | Embeds candidate suppliers as capability vectors and ranks market alternates by cosine similarity, checking each lead time against days-to-ROJ. |
| `agents/llm.py` | Single Gemini configuration (free-tier `gemini-flash-lite-latest`) with rate limiting, plus a disk-backed response cache keyed on `sha256(model\|temperature\|prompt)`. Free-tier latency is variable (measured 1s–153s for the same prompt), so identical prompts are served instantly; a miss always calls the real model, and since every prompt embeds the data it reasons over, changed data changes the key. |
| `agents/query_agent.py` | LangGraph pipeline: classify → NL→Cypher → execute with self-correction → grounded answer + citations + a step trace. |
| `agents/cascade_agent.py` | Parses a natural-language "what-if", calls the deterministic cascade, and narrates the computed facts (cannot invent a number). Also `narrate_scene()`, which explains the live on-screen simulator state. |
| `agents/kg_builder.py` | Uncertainty-guided KG construction from raw documents: extract → score by source reliability → resolve conflicts by weight → write confidence/evidence to Neo4j. Also manages the corpus (list / upload / reset), keeping user uploads separate from the git-tracked seed documents. |
| `agents/brain.py` | Routes a question: a live `scene` wins outright, else delay what-ifs → cascade agent, everything else → query agent. The scene check is deliberately *before* the what-if regex, since scene text contains "delayed"/"slip" and would otherwise be misrouted. |

Design principle: the LLM never produces schedule numbers. It classifies, writes Cypher, and
narrates facts the deterministic engine computed — the property that makes the output auditable.

## API layer (`backend/main.py`, FastAPI)

Thin endpoints over the brain, returning JSON: `/api/project`, `/api/materials`,
`/api/cascade`, `/api/cascade-multi`, `/api/risk`, `/api/montecarlo`,
`/api/alt-supplier/{id}`, `/api/ask`, `/api/build-graph`, corpus management
(`/api/docs`, `/api/docs/upload`, `/api/docs/reset`) and project management
(`/api/projects` …). CORS is scoped to the dev frontend; a startup hook loads the active
project into Neo4j and warms the LLM on a background thread.

Uploads are `.txt` only, capped at 200KB, filename-sanitised and force-prefixed `uploaded_`
so they can never overwrite the seed corpus — which is what makes "reset to demo corpus" a
safe, exact restore.

## Frontend (`web/`)

React + TypeScript + Vite + Tailwind + Framer Motion + React Flow. A marketing **landing
page** and a **dashboard** with five tools — Cascade Simulator (an interactive React Flow
graph that lights up the critical path), Risk Radar, Ask Foreman (chat + reasoning trace),
Build from Docs, and New Project. A typed API client (`src/lib/api.ts`) is the single
integration point; a floating assistant is available on every page.

Two cross-cutting pieces:

- **Onboarding tours** (`src/features/tour/`) — a once-per-screen spotlight walkthrough.
  `TourTarget` measures a real element, `TourOverlay` dims around it with four panels (a
  cutout without SVG masking), and "Replay tutorial" in the sidebar re-runs the current
  tool's tour on demand.
- **Scene-aware chat** (`src/lib/scene.ts`) — the Cascade tool publishes its live state to
  `sessionStorage`; both Ask surfaces send it as `scene`, so the assistant explains what is
  actually on screen rather than re-querying the static graph. Cleared on unmount.

Two deliberate guards in `GraphCanvas.tsx`, both against the same symptom (nodes render,
**0 edges**, no console error — "the graph went blank"):

- **Edges are released one frame after mount.** React Flow resolves each edge against its
  source/target in an internal node store and drops it permanently, without error, if those
  nodes aren't registered yet. Passing nodes and edges in the same first commit lost that
  race on ~1 load in 3; `onInit` + `requestAnimationFrame` closes it.
- **Highlight sets are memoised on content keys.** `delayedIds`/`slippedIds` built inline as
  `new Set(...)` were fresh objects every render, invalidating the node/edge memo forever and
  keeping React Flow permanently re-syncing.

Slider-driven delay values are also debounced (150ms) before they reach the network call and
the graph, so a drag doesn't fire a request per pixel.

## Data model & projects

A project is one JSON shape — `suppliers`, `materials`, `activities` — where activities
reference the materials they need and the activities they depend on by id. Users create
projects through a guided form (`src/projects.py` + the New Project tool); the backend
backfills every engine-required field and loads the project into Neo4j, so the whole app runs
on it. Projects are stored under `data/projects/` with one marked active.

## Integration notes

### Runtime footprint

What Foreman needs in order to run, which is what decides where it can live:

| Dependency | Required? | Notes |
|---|---|---|
| **Neo4j** | for full function | Source of truth and the surface the NL→Cypher agent queries. Without it, `get_graph()` falls back to project JSON — the CPM engine, risk radar, Monte Carlo, recovery and money layers all still work; the query agent does not |
| **Gemini (LLM)** | for the agent layer only | No key → `/api/ask` and document ingest are unavailable. Every deterministic number is unaffected |
| **Python 3.11+** | yes | FastAPI + uvicorn, NetworkX, numpy |
| **Filesystem** | yes | `data/projects/*.json`, the document corpus, and the LLM disk cache |

**State held:** the Neo4j graph, per-project JSON files with an active-project
pointer, uploaded documents, and a disk-backed LLM response cache. The API
process itself is otherwise stateless — the graph is rebuilt from Neo4j on
demand.

### Where this could land in Kaya

The open question is whether Foreman becomes its own service, folds into
`ai-service`, or becomes a capability inside `amber-service`. The relevant
facts, without a recommendation:

- **Language.** Foreman is Python (FastAPI, NetworkX, numpy, LangGraph).
  `ai-service` is Python; `amber-service` is TypeScript/Fastify. On language
  alone, `ai-service` is the closer fit and `amber-service` would mean a rewrite
  of the engine or a service call across the boundary
- **Storage is the real question.** Foreman needs a graph store. `ai-service`
  has none, and Kaya's model is org-per-schema Postgres. Whether a graph
  database is acceptable alongside that is an architecture decision, not an
  implementation detail — it is the thing to settle first, because everything
  else follows from it
- **The engine is separable.** `src/` is pure Python with no web framework and
  no database import outside `db.py`. The CPM cascade, risk radar, Monte Carlo,
  recovery and money layers are callable as a library. If the graph question
  resolves against a graph database, the reasoning could in principle run over
  a different store — the cost is rewriting `db.py` and losing the NL→Cypher
  query agent, which is genuinely tied to Cypher
- **What has to be added regardless of where it lands:** authentication, org
  scoping, and multi-project isolation. None of the three exist today. See
  [`LIMITATIONS.md`](LIMITATIONS.md)

### Ingest boundaries

Foreman consumes P6 schedule data and supplier/vendor logs. It does not own
either ingest. Today it builds its graph from its own project JSON shape, so
anything upstream needs mapping into that shape — or the graph builder needs
pointing at the real sources. Nothing here has been exercised against real P6
output.

## Research grounding

- KG + LLM iterative reasoning — arXiv 2507.17273 (the query agent).
- Uncertainty-guided KG construction (Helicase) — arXiv 2605.26835 (the KG builder).
- Bayesian–Monte-Carlo schedule updating — arXiv 2605.17608 (the risk model).
- GNN supply-network risk — Kosasih & Brintrup (alternate-supplier recovery).
- Critical Path Method — the deterministic cascade engine.

## Running it

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cd web && npm install && cd ..
cp .env.example .env          # add a free Gemini key
./dev.sh                      # Neo4j + API :8000 + web :5173
```
