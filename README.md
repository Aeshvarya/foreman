<p align="center">
  <img src="assets/foreman-logo.png" alt="Foreman logo" width="140">
</p>

<h1 align="center">Foreman</h1>

**The reasoning brain for construction supply chains.**

Everyone predicts *if* a material is late. Foreman predicts **what it breaks** — which downstream activities slip, whether the handover date survives, how confident it is, and what to do about it — in plain English, over a knowledge graph it builds itself from your project documents.

> Kaya AI IIT India Hackathon 2026 · **Team Gozers** (Aeshvarya Awasthi + Varunika Rai, IIT Jodhpur) · Track: **Supply Chain** · **Stage 2**

---

## The problem

On mission-critical builds like data centers, the moment materials are ordered, visibility collapses: What's approved? What's being fabricated? What's delayed? Will it arrive by its **ROJ (Required-On-Job) date**? Answers live in emails, calls and disconnected systems — so slippage is caught **too late**, and one late item cascades: late steel blocks concrete, which blocks MEP, which moves the handover. Megaprojects average **~79% cost overruns**, with material slippage a leading driver.

A delay-prediction dashboard is a warning light. It can't tell you *why*, *what else breaks*, or *how sure it is*. **Foreman is not a dashboard — it's a reasoning brain.**

## What Foreman does

Foreman fuses three ideas nobody has assembled for construction: **uncertainty-aware agentic knowledge-graph construction**, **NL→graph reasoning**, and **CPM-grounded delay-cascade reasoning** — every number grounded in real schedule math, never hallucinated.

### 1. It builds its own brain from raw documents — `src/agents/kg_builder.py`
Feed it the messy documents a real project generates (POs, supplier emails, GPS feeds, goods-received notes, submittal logs). It extracts source-tagged facts, scores each by how trustworthy the source is (site GRN 99% > GPS 95% > supplier email 90% > verbal 75% > inferred queue 60%), and **resolves conflicts by source weight**. On the demo corpus it catches that the switchgear supplier's email ("arrives Aug 20") conflicts with the factory-queue model ("Aug 24"), keeps the higher-weight source, drops confidence to **72%**, and flags it for human check. *Auditable intelligence, not a black box.* (Helicase-style, arXiv 2605.26835.)

### 2. Ask it anything, in English — `src/agents/query_agent.py`
A LangGraph agent classifies the question, writes read-only **Cypher** against Neo4j, self-corrects on error, and answers with citations — showing every step of its reasoning. *"If the diesel generators are delayed, what activities are affected?"* → it traverses the graph and names ACT-7, 8, 11, 12. (KG+LLM iterative reasoning, arXiv 2507.17273.)

### 3. The cascade engine — the star — `src/cascade.py` + `src/agents/cascade_agent.py`
A real Critical-Path-Method forward pass honoring both the dependency network *and* material arrival constraints. Ask *"the switchgear slips 5 days — what breaks?"* and it computes which activities slip and by how much, which **absorb** the hit through float, whether the **handover breaks**, and the cheapest mitigation. The LLM only narrates the numbers the CPM engine computes — so it can never invent a schedule impact.

| Scenario | Foreman's verdict |
|---|---|
| Structural steel +5d (critical path) | 🔴 handover breaks +2d |
| Switchgear +12d | 🟢 float absorbs it — don't panic |
| Generators +14d (60% confidence, submittal stuck) | 🔴 breaks +7d — *the silent killer* |

That contrast **is** the intelligence: a dumb tracker panics at every delay; Foreman knows which delays matter.

### 4. Probabilistic risk, not point estimates — `src/montecarlo.py`
Models each material's arrival as a distribution whose spread scales with our *uncertainty* about it, then runs 3,000 futures through the CPM engine: **14% probability the handover slips, driven almost entirely by the low-confidence diesel generators.** (Bayesian–Monte-Carlo schedule updating, arXiv 2605.17608.)

### 5. Who else can supply it — `src/alt_supplier.py`
When a material threatens the handover, Foreman embeds candidate suppliers as capability vectors (reliability, speed, region) and ranks market alternates — checking each lead time against days-to-ROJ. It knows a full re-order is too slow this late and surfaces the realistic move: a **rental bridge that still meets the deadline**. (Supply-network link-prediction line, Kosasih & Brintrup.)

### 6. Proactive risk radar — `src/risk.py`
Binary-searches the cascade engine for each material's **breaking point** (minimum slip that kills the handover), crosses it with confidence, and ranks the silent killers so you chase the right vendor today.

## Architecture

```
                    Streamlit UI (app.py) — cascade · radar · Ask Foreman · Build-from-Docs
                                     │
   KG Builder ───────► Query agent ───────► Cascade agent   (LangGraph + Gemini)
   (docs→facts,        (NL→Cypher,          (CPM + Monte-Carlo
    confidence,         self-correct,        + NL narration)
    conflicts)          citations)
        │                    │                     │
        └──────────────► Neo4j (Docker) ◄──────────┘
                             │
             NetworkX mirror (src/db.py) → deterministic CPM math
```

Neo4j is the source of truth and the surface the query agent targets; a NetworkX mirror rebuilt from it runs the proven CPM cascade unchanged. `tests/test_mirror.py` proves the two produce identical results.

## Run it

```bash
# 1. Neo4j
docker compose up -d

# 2. Python env
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt

# 3. Gemini key (free — https://aistudio.google.com/apikey)
cp .env.example .env    # then paste your key into GEMINI_API_KEY

# 4. Load the graph + run
./.venv/bin/python -m src.db --load
./.venv/bin/streamlit run app.py
```

## Tech stack

Python · **Neo4j** (Cypher) · **LangGraph** · **Gemini** (via langchain-google-genai) · NetworkX (CPM) · NumPy (Monte-Carlo) · Streamlit + Plotly · Docker

## Demo data

`data/project.json` — **Sunrise DC-1**, a synthetic 12MW data-center build (8 materials, 6 suppliers, 12 activities → handover). `data/docs/` — the raw document corpus the KG Builder ingests. `data/market_suppliers.json` — the alternate-supplier catalog. All synthetic, modeled on real construction supply-chain structures.

## How it extends Kaya

Kaya's Amber unifies submittal → delivery into a project graph. Foreman is the **reasoning layer on top**: it takes that visibility and answers the question a director actually asks — *what breaks if this is late, how sure are we, and how do we save the date?*

---

**Team Gozers** — Aeshvarya Awasthi · Varunika Rai · IIT Jodhpur
