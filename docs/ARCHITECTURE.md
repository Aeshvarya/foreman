# Foreman — Architecture

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
| `alt_supplier.py` | Embeds candidate suppliers as capability vectors and ranks market alternates by cosine similarity, checking each lead time against days-to-ROJ. |
| `agents/llm.py` | Single Gemini configuration (free-tier `gemini-flash-lite-latest`) with rate limiting. |
| `agents/query_agent.py` | LangGraph pipeline: classify → NL→Cypher → execute with self-correction → grounded answer + citations + a step trace. |
| `agents/cascade_agent.py` | Parses a natural-language "what-if", calls the deterministic cascade, and narrates the computed facts (cannot invent a number). |
| `agents/kg_builder.py` | Uncertainty-guided KG construction from raw documents: extract → score by source reliability → resolve conflicts by weight → write confidence/evidence to Neo4j. |
| `agents/brain.py` | Routes a question to the cascade agent (delay what-ifs) or the query agent (everything else). |

Design principle: the LLM never produces schedule numbers. It classifies, writes Cypher, and
narrates facts the deterministic engine computed — the property that makes the output auditable.

## API layer (`backend/main.py`, FastAPI)

Thin endpoints over the brain, returning JSON: `/api/project`, `/api/materials`,
`/api/cascade`, `/api/risk`, `/api/montecarlo`, `/api/alt-supplier/{id}`, `/api/ask`,
`/api/build-graph`, and project management (`/api/projects` …). CORS is scoped to the dev
frontend; a startup hook loads the active project into Neo4j.

## Frontend (`web/`)

React + TypeScript + Vite + Tailwind + Framer Motion + React Flow. A marketing **landing
page** and a **dashboard** with five tools — Cascade Simulator (an interactive React Flow
graph that lights up the critical path), Risk Radar, Ask Foreman (chat + reasoning trace),
Build from Docs, and New Project. A typed API client (`src/lib/api.ts`) is the single
integration point; a floating assistant is available on every page.

## Data model & projects

A project is one JSON shape — `suppliers`, `materials`, `activities` — where activities
reference the materials they need and the activities they depend on by id. Users create
projects through a guided form (`src/projects.py` + the New Project tool); the backend
backfills every engine-required field and loads the project into Neo4j, so the whole app runs
on it. Projects are stored under `data/projects/` with one marked active.

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
