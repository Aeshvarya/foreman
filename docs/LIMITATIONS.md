# Foreman — Known Limitations

Everything we know is wrong or missing, written down before you find it.

This is a hackathon POC that won 2nd place at the Kaya AI IIT India Hackathon
national final. It was built to prove an idea in six weeks, not to run in
production. The list below is what stands between it and being a real service.

---

## 🔴 Security

**No authentication on any endpoint**, read or write, including
`POST /api/projects`, `POST /api/docs/upload`, `PUT /api/money`, and
`DELETE /api/projects/{pid}`. Anyone with the URL can read or modify the data
on the hosted instance.

Acceptable for a hackathon deployment on synthetic data. **A blocker for
anything touching client data** — and the reason real project data must stay
off the hosted instance until this is fixed.

No org or tenant concept exists anywhere in the schema or the code.

## 🔴 Scale — never run above 26 nodes

The deployed graph is **26 nodes / 29 edges** for one synthetic project.
A real critical path is 30–40 items out of ~3,000 — one to two orders of
magnitude more than anything this has been exercised on.

Untested at real scale: graph build time, cascade traversal depth, Monte Carlo
cost. No Neo4j indexes or uniqueness constraints exist; fine at 26 nodes, not
fine later.

## 🔴 Never tested against real P6 output

The graph is built from Foreman's own project JSON. Real P6 exports will bring
nulls, duplicate IDs, and activity naming that doesn't match current
assumptions.

## 🔴 `category_of()` is string matching

`alt_supplier.py` maps material names to categories with string matching. It
works because the synthetic dataset was written to match it. **Real vendor
material names will not match, and alternate-supplier recommendations will
silently return nothing rather than erroring.**

This is the single most likely thing to break on first contact with real data.
It already caused a near-miss the day before the hackathon final, when a naming
mismatch would have quietly killed the Recovery feature on stage.

## 🟡 Cost defaults are assumptions, not researched figures

**Resolved 2026-09-04: the engine is now USD-native.** `money.py` computes in
dollars, defaults are a US mission-critical build cost base, and INR is a
display conversion only (fixed rate, stamped 2026-08-21).

The remaining caveat is the honest one: the defaults are **labelled
assumptions**, not researched US market figures. Every one carries
`source: "assumed"` and a `basis` sentence, and every one is user-editable —
but they were scaled from the original Indian cost base with ratios preserved,
not derived from US contract data. A client's real numbers should replace them
before anything commercial is claimed.

## 🟠 Single-project, destructive load

`load_to_neo4j()` runs `MATCH (n) DETACH DELETE n` before loading. One project
at a time, whole database wiped each time. This is a demo pattern and directly
conflicts with any multi-tenant use.

## 🟠 Live-vs-local drift

The deployed instance and the local mirror disagree on at least one figure:
live `p_slip` **0.15** vs local **0.137**. The hosted Neo4j holds slightly
different data than the repo mirror. Unresolved.

`scripts/verify_live_numbers.py --check` exists precisely so this kind of drift
is loud rather than silent.

## 🟠 Document ingest only ever run on 6 seed files

`kg_builder` has processed six bundled text files (GRN, PO, supplier email,
factory queue estimate, GPS tracking, submittal log). Extraction quality at
real volume, on real vendor logs, is unknown.

## 🟡 LLM dependencies

- Gemini free tier. Rate limits are real; `llm.py` adds a limiter and a disk
  cache as insurance
- No key → `/api/ask` and all document ingest are unavailable. The
  deterministic engine still works completely
- Gemini 3.x returns content as a list of parts. Always `invoke_text()`, never
  `.content` raw

## 🟡 Deployment

Render free tier — cold starts are slow enough to matter in a live demo.

## 🟡 Test coverage

Three suites: `test_mirror`, `test_money`, `test_montecarlo` (60+ assertions on
correlated sampling). **The API layer, the agents, the document ingest and `risk.py` (the
deterministic Risk Radar) have no automated tests.**

---

## What is genuinely solid

For balance — these have been exercised hard and hold up:

- **The CPM cascade math.** Real forward-pass scheduling over both dependency
  and material-arrival constraints. Not a mock
- **Grounding.** Every number an agent reports comes from a deterministic
  function. The LLM phrases already-computed facts and cannot invent a
  schedule impact
- **Confidence propagation.** Source-weighted, conflict-resolving, and visible
  in the output
- **Correlated Monte Carlo.** Same-supplier materials no longer fail
  independently; ρ=0 reproduces the previous model bit for bit, and marginals
  hold across 40k draws per material
- **`NUMBERS.md` + `verify_live_numbers.py`.** Every published figure is
  generated from the live deployment, never typed, and `--check` fails if the
  committed doc has drifted
