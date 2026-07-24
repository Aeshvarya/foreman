# Foreman — Live Demo Script (~2.5 min)

The demo has ONE hero (the delay cascade) and three supporting beats. Keep it
tight. Every number on screen comes from real math — say so.

**Setup before recording/presenting:**
```bash
docker compose up -d && ./.venv/bin/python -m src.db --load
./.venv/bin/streamlit run app.py
```
Have the app open on the **Delay Cascade Simulator** tab.

---

## 0 · Hook (10s)
> "On a data-center build, one late material can silently move the handover date
> by weeks — and nobody finds out until it's too late. Foreman is the reasoning
> brain that catches it. Not a dashboard that predicts *if* something's late —
> a brain that tells you *what it breaks.*"

## 1 · The cascade — the hero (45s) — *Delay Cascade Simulator*
- Pick **Structural steel package (MAT-1)**, slide to **5 days**.
- "Steel slips 5 days — watch." The graph lights the **red critical path** to the handover.
- Read the verdict: **"Handover breaks, +2 days."** Point at the slipped-activity cards.
- Now pick **Switchgear (MAT-2)**, slide to **12 days**. Verdict flips to **green — float absorbs it.**
- > "Same 'delay', opposite answer. A dumb tracker panics at both. Foreman knows
>   which delays actually matter — because it's running real critical-path math
>   over the schedule, not guessing."

## 2 · Ask it in English (35s) — *Ask Foreman*
- Click the chip **"If the diesel generators are delayed, what activities are affected?"**
- While it runs, open the **🧠 reasoning trace**: "It classified the question, wrote
  this Cypher against the graph, ran it, and answered — with citations."
- Read the answer (ACT-7, 8, 11, 12). > "No dashboards, no clicking. You ask, it reasons."
- Optional: type **"What if the switchgear slips 12 days?"** → it routes to the cascade brain and narrates the grounded result.

## 3 · It builds its own brain — the differentiator (40s) — *Build from Docs*
- > "Real projects don't have clean data. So Foreman reads the mess."
- Click **Build knowledge graph from documents**.
- When it lands: **6 documents → facts → 1 conflict caught.**
- Point at the conflict banner: > "The supplier's email says the switchgear arrives
>   August 20. The factory-queue model says the 24th. Foreman caught the
>   disagreement, trusted the stronger source, dropped its confidence to 72%, and
>   flagged it for a human. That's auditable intelligence — not a black box."

## 4 · The director's answer (25s) — *Risk Radar*
- Top banner: **"Monte-Carlo: 14% chance the handover slips… biggest driver: the diesel generators."**
- > "Across 3,000 simulated futures, one material carries almost all the risk —
>   the generators. Low confidence, submittal stuck, little slack."
- Scroll to the radar: generators ranked **CHASE TODAY**.
- (If time) mention the cascade tab's **alternate-supplier bridge**: "a full re-order
  is too slow, but a rental bridge still hits the date."

## 5 · Close (15s)
> "Kaya's Amber tells you where your material is. Foreman tells you what breaks if
> it's late, how sure it is, and how to save the date — a reasoning layer that
> sits right on top of the platform. That's Foreman."

---

### One-liners to have ready for judge Q&A
- **"How is the +7 days computed?"** — CPM forward pass over the dependency graph + material arrival constraints; the LLM only narrates the number, never invents it.
- **"Is the graph real or hardcoded?"** — Built by the KG Builder from the document corpus, with per-fact confidence; structure persists in Neo4j.
- **"What's the confidence based on?"** — Source reliability weighting; conflicts lower it. Shown on every answer.
- **"Does this need Kaya?"** — No — it's standalone on synthetic data, but designed to extend Amber's project graph.
