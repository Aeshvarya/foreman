# Foreman — Risk Radar: Implementation

> **Integration target.** The kickoff named the Risk Radar as one of the things
> the Kaya integration must surface, alongside impacting schedule and
> critical-path items. This document is the implementation detail for that
> feature specifically.

The Risk Radar is Foreman's *proactive* half. The cascade engine answers
"something slipped — what breaks?" The Risk Radar answers the question nobody
has asked yet: **"what is about to hurt me, and does anyone actually know where
it is?"**

It is two independent engines presented as one feature:

| Engine | File | Answers |
|---|---|---|
| **Deterministic radar** | `src/risk.py` (97 lines) | "How many days can each material slip before the handover breaks, and how sure are we of its status?" |
| **Probabilistic radar** | `src/montecarlo.py` (161 lines) | "What is the probability the handover slips at all, how far, and which material is driving it?" |

Both run over the same graph and the same CPM engine (`cascade.py`), so they
can never disagree about the schedule itself.

---

## Worked example

Both engines, run on the bundled demo project ("Sunrise DC-1", 8 materials,
baseline handover **2026-11-04**). These are real outputs, not illustrations —
reproduce them with `python -m src.risk` and `python -m src.montecarlo`.

### What the deterministic radar returns

| Material | Breaking point | Confidence | Risk score | Verdict |
|---|---|---|---|---|
| **MAT-6** 2MVA diesel generators (×4) | **8 d** | **0.60** | **0.740** | 🔴 CHASE TODAY |
| MAT-1 Structural steel package | **4 d** | 0.92 | 0.528 | 🟠 WATCH CLOSELY |
| MAT-2 4000A LV switchgear lineup | 16 d | 0.70 | 0.516 | 🟡 GET IT CONFIRMED |
| MAT-5 Precast concrete wall panels | 7 d | 0.99 | 0.431 | 🟠 WATCH CLOSELY |
| MAT-8 Busway / busbar trunking | 21 d | 0.75 | 0.400 | 🟢 FINE |
| MAT-7 Fire suppression (NOVEC skid) | 23 d | 0.88 | 0.303 | 🟢 FINE |
| MAT-3 CRAC cooling units (×8) | 36 d | 0.95 | 0.110 | 🟢 FINE |
| MAT-4 MV/LV power cabling | **never** | 0.99 | 0.000 | 🟢 FINE |

### Reading it

**The top row is the whole point of the feature.** The diesel generators are
*not* the tightest item on the project — the structural steel is, at 4 days
versus 8. But the generators rank first, and the reason is provenance:

```
MAT-6  confidence 0.60  "submittal still under review — fabrication
                          cannot start; arrival inferred"
MAT-1  confidence 0.92  "supplier confirmation email + fab photos"
```

The steel is tight **and known**. The generators are tight **and nobody has
confirmed anything** — their arrival date is an inference, not a fact. That is
the silent killer: the item that looks fine on a risk register because no one
has reported a problem, precisely because no one has looked.

The arithmetic, for MAT-6:

```
exposure = 1 - (8 / 45)              = 0.822
score    = 0.822 × (1.5 - 0.60)      = 0.740
```

and for MAT-1:

```
exposure = 1 - (4 / 45)              = 0.911   ← more exposed
score    = 0.911 × (1.5 - 0.92)      = 0.528   ← but less risky
```

Higher exposure, lower score. **Confidence is what separates them**, and it is
why the verdict ladder checks the 🔴 rule (`bp ≤ 10` *and* `conf < 0.8`) before
the 🟠 rule — otherwise the generators would be downgraded to "watch closely"
by the same threshold that catches the steel.

At the other end, **MAT-4 scores exactly 0.000**: it is already delivered
(confidence 0.99, source "site GRN"), and no delay within 45 days moves the
handover. `breaking_point()` returns `None`, `exposure` is forced to 0, and it
drops off the radar entirely. Nothing to chase.

### What the probabilistic radar returns

```
n = 3000 · vendor_correlation = 0.4 · baseline handover 2026-11-04

P(handover slips)  0.129
mean slip          0.4 days
P50 / P90 slip     0.0 / 1.0 days

top risk drivers
  MAT-6  2MVA diesel generators        0.596
  MAT-1  Structural steel package      0.015
  MAT-2  4000A LV switchgear           0.000
  MAT-3  CRAC cooling units            0.000
```

**The two engines agree, and they got there independently.** The deterministic
radar ranked MAT-6 first by crossing schedule slack with provenance. Monte
Carlo never looks at that score — it samples 3,000 futures and measures which
material's sampled delay actually correlates with the handover moving. It also
lands on MAT-6, at **0.596 against 0.015 for everything else.**

That is the useful shape of the answer: the project is *probably* fine
(P50 = 0 days, so in more than half of futures the date holds), but **there is
a 13% chance it slips, and essentially all of that risk is one vendor's
generators.** A director gets a number; a site manager gets one phone call to
make.

Note also **P50 = 0 while mean = 0.4**. The distribution is not symmetric —
most futures are fine and a minority are late — which is exactly the asymmetry
the late bias is there to model.

### Seeing vendor correlation do its job

Re-run with correlation switched off:

```
rho = 0.4  →  P(slip) = 0.129
rho = 0.0  →  P(slip) = 0.137
```

Same engine, same seed, same graph. With materials sampled independently, the
generators' four units can cancel each other out — one early, one late — and
the model reports a *different* risk than when a single vendor-level event
moves all of them together. Neither number is "wrong"; the point is that the
independence assumption was silently making a choice, and now it is an explicit,
reported parameter (`vendor_correlation` comes back on every result).

> This is also the fastest way to sanity-check a port: if `rho = 0` does not
> reproduce the independent model exactly, the RNG streams have been crossed.

---

## Part 1 — Deterministic radar (`src/risk.py`)

### The idea
Two numbers per material, crossed:

1. **Breaking point** — the smallest delay that moves the handover date
2. **Confidence** — how sure we are of its current status

A material with a **low breaking point and low confidence** is a *silent
killer*: almost no room to slip, and nobody has confirmed where it is. That is
the vendor to chase today.

### Breaking point — binary search over the cascade

```python
def breaking_point(g, material_id, max_days=MAX_PROBE_DAYS) -> int | None:
    lo, hi, answer = 1, max_days, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if run_cascade(g, material_id, mid).handover_slip_days > 0:
            answer, hi = mid, mid - 1
        else:
            lo = mid + 1
    return answer
```

**The cascade is monotonic in delay** — if a 5-day slip breaks the handover,
so does a 6-day slip — which is what makes binary search valid. `MAX_PROBE_DAYS
= 45`; `None` means the material never breaks the handover within that range.

Cost: **O(log 45) ≈ 6 cascade runs per material.** For the 26-node demo graph
that is trivial. At 30–40 critical-path items it is 180–240 forward passes per
radar refresh — see *Scale* below.

### Risk score

```python
exposure = 0.0 if bp is None else max(0.0, 1 - (bp / MAX_PROBE_DAYS))
score    = round(exposure * (1.5 - conf), 3)
```

- **`exposure`** rises as the breaking point tightens. A 2-day breaking point
  scores ~0.96; a 40-day one scores ~0.11; never-breaks scores 0
- **`(1.5 - conf)`** is the uncertainty multiplier. It is deliberately *not*
  `(1 - conf)`: even a fully-confirmed material (conf 1.0) keeps a 0.5
  multiplier, because a tight breaking point is dangerous whether or not
  anyone is sure about it. Uncertainty *multiplies* exposure; it doesn't
  create it

Results are sorted by descending score.

### Verdicts

Written for site staff, not schedulers — they say what to do and why, in words
a foreman would use. No "float", no "slack".

| Condition | Verdict |
|---|---|
| `bp ≤ 10` **and** `conf < 0.8` | 🔴 **CHASE TODAY** — barely any room, and nobody has confirmed where it is |
| `bp ≤ 7` | 🟠 **WATCH CLOSELY** — this one decides the handover date |
| `conf < 0.75` | 🟡 **GET IT CONFIRMED** — no firm update, though there is some room |
| otherwise | 🟢 **FINE** — enough room to take a slip without moving the date |

Note the ordering: the 🔴 rule is checked first, so a material that is both
tight *and* unconfirmed never gets downgraded to 🟠.

### Output

```python
@dataclass
class MaterialRisk:
    material_id: str
    name: str
    supplier: str
    breaking_point_days: int | None   # None = never breaks within 45 days
    confidence: float
    confidence_source: str            # where the confidence came from
    risk_score: float
    verdict: str
```

`confidence_source` is the honesty field — it travels with every number so the
UI can show *why* we believe a status (`user-entered`, an extracted document, an
inferred estimate) rather than just asserting it.

---

## Part 2 — Probabilistic radar (`src/montecarlo.py`)

### The idea
The deterministic radar assumes an exact delay. Real projects aren't exact. So
model each material's arrival as a **distribution whose spread scales with our
uncertainty about it**, then push thousands of futures through the same CPM
engine.

### Turning confidence into a distribution

```python
MAX_STD_DAYS  = 12.0     # a material we know nothing about
LATE_BIAS_DAYS = 6.0     # estimates in construction are optimistic

def _material_params(node):
    if node.get("shipment_status") == "delivered":
        return 0.0, 0.0                       # nothing left to vary
    uncertainty = 1.0 - float(node.get("confidence", 0.7))
    return LATE_BIAS_DAYS * uncertainty, MAX_STD_DAYS * uncertainty
```

- A **delivered** material contributes zero variance — it has already arrived
- confidence **0.99** → bias 0.06d, std 0.12d (barely moves)
- confidence **0.60** → bias 2.4d, std 4.8d (swings wide)

**The late bias is deliberate and asymmetric.** Construction estimates are
optimistic; a symmetric distribution would model a world where deliveries are
as likely to be early as late, which is not the world.

### Vendor correlation — the part that matters

```python
VENDOR_CORRELATION = 0.4
```

**Materials from one vendor do not fail independently.** A plant fire, a
strike, a customs backlog — one event moves everything that vendor ships.
Sampling them independently lets the late ones cancel the early ones, which
quietly thins the tail: *the model looks safer than the project is.*

Each material's draw is split into a shock its whole vendor feels and a shock
only it feels:

```python
w_shared, w_private = sqrt(rho), sqrt(1 - rho)
d_days = bias + std * (w_shared * vendor_shock + w_private * private_draw)
```

Those weights are chosen because they leave **every material's own mean and
standard deviation untouched** — individual delivery forecasts do not move,
only the joint behaviour does.

Two implementation details worth keeping if this is ported:

- **`rho = 0` reproduces the previous independent model bit for bit.** Vendor
  shocks are drawn from a *separate* RNG stream (`seed + 1`), so per-material
  draws stay the same numbers in the same order. That is what makes the
  regression test exact rather than approximate
- **A material with no supplier gets its own synthetic vendor**
  (`__unshared__{mid}`), so orphans stay independent instead of being lumped
  together into one fake correlated group

### Risk drivers

A material's contribution is the **correlation between its sampled delay and
the resulting handover slip**, clamped at 0:

```python
corr = np.corrcoef(delays[mid], slips)[0, 1]
```

This is the honest measure: it ranks by *how much this material actually moves
the date across thousands of futures*, not by how loudly it is flagged. A
high-variance material that sits nowhere near the critical path correctly
scores ~0.

### Output

```python
@dataclass
class MCResult:
    n: int                       # simulations run (default 3000)
    p_slip: float                # P(handover finishes later than baseline)
    mean_slip: float
    p50_slip: float
    p90_slip: float
    baseline_handover: str
    drivers: list[dict]          # [{material, name, risk_contribution}]
    vendor_correlation: float    # the rho this run used
```

`vendor_correlation` is returned, not just consumed — every result carries the
assumption that produced it.

### Determinism
`seed = 7` by default, so the same graph produces the same numbers on every
run. **A demo that re-prices itself between two runs is a demo nobody can
check.**

---

## API

```
GET /api/risk         → list[MaterialRisk]   (deterministic radar)
GET /api/montecarlo   → MCResult             (probabilistic radar)
```

Both take no parameters and operate on the active project. See `API.md`.

⚠️ Neither endpoint is authenticated. See `LIMITATIONS.md`.

---

## Tests

`tests/test_montecarlo.py` — 60+ assertions:

- `rho = 0` reproduces the pre-correlation model **exactly**
- Marginals hold across 40,000 draws per material at `rho` = 0.4 / 0.8 / 1.0
- Same-vendor pairs correlate to within ±0.05 of `rho`; different-vendor pairs
  stay under 0.05
- `rho` outside [0, 1] is rejected
- P90 ≥ P50 at every `rho`; the baseline handover is never mutated

`risk.py` has **no dedicated test suite** — a real gap, listed in
`LIMITATIONS.md`.

---

## Integration notes for Kaya

### What it needs
Only the graph. Both engines are pure Python over `cascade.forward_pass` and
the NetworkX mirror — **no LLM, no network, no Neo4j call of their own.** If
the graph is in memory, the radar runs. That makes this the *easiest* part of
Foreman to embed: it is a library call, not a service.

### The fields it depends on
| Field | On | Used by |
|---|---|---|
| `confidence` | material | both engines — the whole model rests on it |
| `confidence_source` | material | radar output (provenance) |
| `shipment_status` | material | Monte Carlo (`delivered` → zero variance) |
| `expected_arrival` | material | Monte Carlo baseline |
| `supplier` | material | vendor correlation grouping |
| `duration_days`, `depends_on`, `needs_materials` | activity | CPM forward pass |

🔴 **`confidence` is the hard dependency.** If Kaya's vendor-log data does not
carry a per-material confidence, the deterministic radar still works (breaking
point is pure schedule math) but **the risk score, the verdicts and the entire
Monte Carlo model degrade to guesswork.** Mapping Kaya's data onto a confidence
value — or deriving one from source type, as `kg_builder` already does — is the
first integration question to answer.

### Scale
`risk_radar()` runs ≈6 cascade probes per material, and each probe is a full
CPM forward pass. Monte Carlo runs `n` forward passes (default 3000) plus one
per material per iteration.

At 26 nodes this is instant. At 30–40 critical-path items out of ~3,000 the
forward pass itself gets larger, and **Monte Carlo cost scales with graph size ×
iterations**. The kickoff worried this would be prohibitive; scoping to the
critical-path subset keeps the simulation set manageable, but **neither engine
has been profiled at real scale.** That is exactly what the "real-scale graph
spike" is for.

Cheap levers if it turns out too slow: lower `n`, cache the baseline forward
pass, or probe breaking points only for materials above a risk floor.

### What has to be added
- **Auth and org scoping** — neither engine has any concept of a tenant
- **A confidence source for real data** — see above
- **Thresholds are hardcoded** (`bp ≤ 10`, `conf < 0.8`, `MAX_PROBE_DAYS = 45`,
  `VENDOR_CORRELATION = 0.4`, `MAX_STD_DAYS = 12`, `LATE_BIAS_DAYS = 6`). These
  are tuned for the synthetic dataset and should become configuration before
  they meet a real project
- **A test suite for `risk.py`**
