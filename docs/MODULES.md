# Foreman — Module Reference

Implementation detail, module by module. Written for an engineer who has to
maintain or extend this code, not for someone evaluating it.

Layout:

```
app.py                  Streamlit UI (legacy fallback — not the demo surface)
backend/main.py         FastAPI app, 27 endpoints, serves the built SPA
src/                    the reasoning engine (pure Python, no web framework)
src/agents/             the LLM layer (LangGraph + Gemini)
web/                    Vite/React SPA (the surface Kaya sees)
tests/                  3 suites — mirror, money, montecarlo
scripts/                verify_live_numbers.py
data/                   project JSON, per-project files, seed documents
```

The important separation: **`src/` computes, `src/agents/` narrates.** Every
number an agent reports comes from a deterministic function in `src/`. The LLM
puts already-computed facts into English; it cannot invent a schedule impact.

---

## `src/` — the engine

### `graph.py` (96 lines)
Builds the in-memory NetworkX knowledge graph from project JSON.

Edge direction follows the flow of consequence:
`Supplier → Material → Activity → dependent Activities → handover`.

- `load_project(path)` — read raw project JSON
- `build_graph(project)` — construct the `nx.DiGraph`; nodes carry `kind`
  (`supplier` / `material` / `activity`) plus all their source fields
- `downstream_activities(g, node_id)` — every activity reachable from a node,
  i.e. the potential blast radius
- `graph_summary(g)` — counts for display

### `db.py` (259 lines)
Neo4j store plus the NetworkX mirror. **Neo4j is the source of truth**; the CPM
math runs on a mirror built from it, so the engine works identically with or
without a database.

```
project.json --load_to_neo4j--> Neo4j --graph_from_neo4j--> NetworkX --> CPM
```

- `neo4j_enabled()` — is `NEO4J_URI` configured
- `load_to_neo4j(project)` — wipes and rewrites the graph (`MATCH (n) DETACH DELETE n` first)
- `graph_from_neo4j()` — rebuild the NetworkX mirror from Neo4j
- `get_graph()` — the accessor everything else calls; falls back to JSON when Neo4j is absent
- `run_cypher(query, params)` — raw Cypher, used by the query agent
- `update_material(mat_id, props)` — write extracted facts back
- `verify(silent)` — node/edge counts plus a sample query

CLI: `python -m src.db --load` / `--verify`

### `cascade.py` (272 lines) — the core
Critical Path Method scheduling. Real schedule math, not a mock.

1. **Forward pass** computes each activity's earliest start/finish from both its
   dependency network *and* its material arrival constraints
2. A delay scenario shifts one material's arrival and re-runs the pass
3. The **diff** between baseline and scenario is the cascade

- `forward_pass(g, ...)` — earliest start/finish for every activity
- `run_cascade(g, material_id, delay_days)` → `CascadeReport`
- `run_cascade_multi(g, delays)` — several materials delayed at once
- `format_report(r)` — human-readable rendering
- Dataclasses: `ActivitySchedule`, `CascadeReport`

### `risk.py` (97 lines) — the risk radar
> 📄 **Full implementation detail: [`RISK-RADAR.md`](RISK-RADAR.md)** — this is a named Kaya integration target.
Scans every material and asks two questions:

1. **Breaking point** — how many days can this slip before the handover breaks?
   (computed by probing the cascade engine, not estimated)
2. **Confidence** — how sure are we of its current status?

Low breaking point + low confidence = the *silent killers*. Those are the
vendors to chase today.

- `breaking_point(g, material_id, ...)`
- `risk_radar(g)` → `list[MaterialRisk]`

### `montecarlo.py` (161 lines)
> 📄 **Full implementation detail: [`RISK-RADAR.md`](RISK-RADAR.md)**
The deterministic cascade answers *"if X slips exactly N days."* Real projects
aren't that certain. Each material's arrival is modelled as a **distribution
whose spread scales with our uncertainty**: a delivered material (confidence
≈0.99) barely moves; an inferred one (0.6) swings wide.

Simulates thousands of futures through the same CPM engine and returns
P(slip), the slip distribution (mean / P50 / P90), and each material's
contribution to the risk.

- `simulate(g, n=3000, seed=7, ...)` → `MCResult`
- `_material_params(node)` — confidence → distribution parameters

⚠️ Materials from the **same supplier are correlated**, not independent — added
after the hackathon deck was written.

### `recovery.py` (283 lines)
Stops reporting the problem and prices the fixes. Generates realistic ways to
claw days back, each with a cost, so the choice is obvious to someone who has
never opened a Gantt chart.

- `recovery_options(delays, project)` — the ranked option set
- `_expedite_option(...)` — air-freight / expedite
- `_switch_option(...)` — alternate supplier
- `_overtime_options(...)` — night shift / extra crew
- Always includes **"do nothing"** with its own cost

### `timemachine.py` (272 lines) — the cost of waiting
Proves the "early enough to do something cheap" claim rather than asserting it.
The insight is physical: **recovery options decay with time.** An alternate
supplier needing 24 days is a real option today and impossible in three weeks,
because the date they must hit has not moved.

- `cost_of_waiting(material_id, delay_days, ...)`
- `_best_option(...)` — best available option at a given as-of date
- `_expedite_capacity(...)` — how much expediting can still buy
- Returns checkpoints showing options expiring over time

### `money.py` (265 lines)
Converts schedule facts into cash. Two design rules, both load-bearing:

1. **Every number is either the user's or a labelled assumption** — each line
   carries `source` (`"your number"` / `"assumed"`) and a `basis` sentence
2. **Every number shows its arithmetic** — each line carries a `formula` string

- `cost_of_delay(slip_days, project)`
- `commercials(project)` / `values(project)` / `defaults()`
- `set_currency(code)` / `currency()` / `rate_info()`
- `clean_patch(patch)` — validate user edits
- `fmt_money` / `fmt_inr` / `fmt_usd`

**Base unit is USD.** Defaults are a US mission-critical build cost base; INR is a display conversion at a fixed, date-stamped rate. `fmt_money()` is the only place that decides which the reader sees.

### `alt_supplier.py` (113 lines)
When a material is at risk, the next question is always *"who else can supply
this, fast enough?"* Embeds every candidate supplier as a capability vector
(reliability, speed, region proximity) and ranks alternates in the same
category by cosine similarity to the ideal profile, then checks each one's lead
time against the days actually remaining.

A lightweight, explainable stand-in for a GNN over the supply network.

- `category_of(material_name)` — ⚠️ **string-matching on material names.** This
  is the piece most likely to break on real data (see `LIMITATIONS.md`)
- `recommend(material_id, k=2)`

### `today.py` (184 lines) — the morning brief
Inverts the tool: instead of waiting to be driven, it walks the project, asks
the engines what a good PM would ask, and returns a ranked list of sentences a
non-technical person can act on.

- `brief(project)` — the ranked brief
- `_urgency(slack, confidence)` — ranking
- `_how_sure(confidence)` — confidence → plain English

### `comms.py` (170 lines) — the last mile
Analysis doesn't move until someone writes to the supplier and warns the
client, and that writing is where good analysis usually dies. So it's drafted.

- `drafts(delays, project)` → supplier message, client message, one-pager
- Supplier register: specific, dated, asks for one thing, no blame
- Client register: early, plain, plan already in it

### `projects.py` (230 lines)
Multiple projects without touching JSON by hand. Each lives at
`data/projects/<id>.json`; `index.json` tracks the list and which is active.
The active project is what gets loaded into Neo4j at startup.

- `list_projects()` / `get_active_id()` / `set_active(pid)`
- `create_project(data)` / `delete_project(pid)`
- `get_active_project()` / `load_project_file(pid)`
- `set_commercials(patch)`
- `_ensure_seed()` — seeds the demo project on first run

---

## `src/agents/` — the LLM layer

### `brain.py` (83 lines) — the router
- Delay "what-if" → **cascade agent** (grounded CPM math)
- Anything else (status, lists, counts, who/where/when) → **query agent** (NL→Cypher)

Both return `{answer, citations, trace, mode}` so the UI renders them identically.

- `answer(question, scene)`

### `cascade_agent.py` (182 lines) — Agent C
Turns *"what if X slips N days?"* into a grounded answer:
`parse intent → run the CPM cascade → narrate what breaks, how sure, cheapest fix`

**Every number comes from `run_cascade`.** The LLM only phrases already-computed
facts. It cannot invent a schedule impact — the property to point at when
someone asks whether the model is making things up.

- `explain_cascade(question, material_id, ...)`
- `narrate_scene(question, scene)` — answers about live on-screen state
- `_parse_intent(question, g)` / `_resolve_material(g, keyword)`

### `query_agent.py` (502 lines) — Agent B
A LangGraph pipeline over Neo4j. Simple lookups take the short path; hard
questions get decomposed and the answer is checked before display:

```
plan → execute (self-correct on error)
     → [diagnostic] decompose → gather evidence
     → answer
     → reflect (is every claim supported?)
         → gather the missing piece → answer again
```

- `QueryState` (TypedDict) — the graph state
- `plan_node` / `execute_node` / `_route_after_execute`
- `_write_cypher(question, prev, err)` — NL → Cypher, with error feedback
- `_gather` / `_cite`

### `kg_builder.py` (257 lines) — Agent A
Builds the confidence-scored graph from messy documents — POs, supplier emails,
GPS feeds, GRNs, submittal logs:

```
extract facts (per doc) → score by source → verify (resolve conflicts
by source weight) → construct (write to Neo4j)
```

Every material's status carries a **confidence** and a **source**. When two
documents disagree (an optimistic supplier email vs an inferred queue model),
`_verify` catches it and resolves by source reliability.

- `build_graph_from_docs(write=True)`
- `_extract(doc_name, text)` / `_verify(facts, g)` / `_weight(source_type)`
- `list_docs()` / `save_uploaded_doc()` / `reset_docs()`

### `project_builder.py` (246 lines)
Builds a whole project from a sentence *or* an existing spreadsheet. Both are
the same problem — messy human input in, a valid project graph out — so both
take the same path: input → text → structured JSON from the model → repair.

- `draft(text)` — sentence → project draft
- `spreadsheet_to_text(filename, content)` — xlsx → text (openpyxl)
- `_parse_json(raw)` / `_repair(data)` — validation and repair

### `llm.py` (203 lines)
One place to configure Gemini for every agent.

- Model: `gemini-flash-lite-latest` (free tier; chosen over `gemini-2.5-flash`,
  which caps at 5 req/min and throttles a live demo)
- Disk-backed response cache + a light rate limiter
- `invoke_text(prompt, temperature, model)` — ⚠️ **always use this.** Gemini 3.x
  returns content as a *list of parts*, never touch `.content` raw
- `has_key()` / `cache_stats()` / `clear_cache()`

---

## `backend/main.py` (446 lines)
FastAPI app: 27 endpoints (see `API.md`), CORS, a currency middleware, and it
serves the built SPA as a catch-all route.

Startup (`_startup`): loads the active project into Neo4j with retries
(`_load_active_into_neo4j`, 8 attempts) and warms the LLM (`_warm_llm`).

## `tests/`
- `test_mirror.py` — the Neo4j → NetworkX mirror matches the JSON source
- `test_money.py` — cost arithmetic
- `test_montecarlo.py` — 60+ assertions pinning correlated sampling against the
  model it replaced (ρ=0 reproduces the old model bit for bit)

## `scripts/verify_live_numbers.py`
Asks the live deployment for every published figure and regenerates
`docs/NUMBERS.md`. `--check` re-reads the deployment and **fails if the
committed doc has gone stale**, so drift becomes loud instead of silent.

**Standing rule: if a number is not in `NUMBERS.md`, it is not claimed.**
