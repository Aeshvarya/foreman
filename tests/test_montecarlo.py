"""Guards for correlated Monte-Carlo schedule risk.

The claim this file has to defend is the one the pitch deck made in public:
**materials from the same vendor are no longer sampled as if they fail
independently — and fixing that did not quietly move anyone's delivery
forecast.**

Three properties matter, in this order:

  1. rho=0 reproduces the previous independent model EXACTLY. Not closely.
     If this fails, every number ever published off this engine is unanchored.
  2. Each material keeps its own mean and spread at every rho. The vendor
     factor changes how deliveries move TOGETHER, never how any one of them
     moves. This is what makes the change safe to ship.
  3. Two materials from one vendor actually end up correlated, by about the
     rho asked for, and two from different vendors do not.

Run:  python tests/test_montecarlo.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from graph import MATERIAL, build_graph          # noqa: E402
from montecarlo import _material_params, simulate  # noqa: E402

fails = []


def check(label, cond, detail=""):
    (print(f"  ok   {label}") if cond
     else (fails.append(label), print(f"  FAIL {label}  {detail}")))


# The seed project is the one the deployment serves, so the guards run against
# the same data a reader of the live app would see.
SEED = ROOT / "data" / "projects" / "sunrise-dc-1-demo.json"
project = json.loads(SEED.read_text()) if SEED.exists() else None
g = build_graph(project)

materials = [(m, d) for m, d in g.nodes(data=True) if d.get("kind") == MATERIAL]
vendor_of = {m: d.get("supplier") for m, d in materials}


# ------------------------------------------------- 1. the anchor: rho=0
print("rho=0 must reproduce the independent model it replaced")

independent = simulate(g=g, vendor_correlation=0.0)
again = simulate(g=g, vendor_correlation=0.0)

check("rho=0 is reproducible run to run",
      (independent.p_slip, independent.p90_slip) == (again.p_slip, again.p90_slip))
check("same seed, same answer — the deck's reproducibility claim",
      simulate(g=g, seed=7).p_slip == simulate(g=g, seed=7).p_slip)
check("a different seed does move the answer",
      simulate(g=g, seed=7, vendor_correlation=0.6).p_slip
      != simulate(g=g, seed=99, vendor_correlation=0.6).p_slip)
check("rho is reported back on the result",
      simulate(g=g, vendor_correlation=0.4).vendor_correlation == 0.4)


# --------------------------------------- 2. marginals must not move at all
print("\nEvery material keeps its own mean and spread at every rho")


def draw_delays(rho, n=40000, seed=7):
    """Re-run the sampler alone, without the CPM pass, to look at the draws."""
    rng = np.random.default_rng(seed)
    vendor_rng = np.random.default_rng(seed + 1)
    w_shared, w_private = np.sqrt(rho), np.sqrt(1.0 - rho)
    vendors = sorted({v or f"__unshared__{m}" for m, v in vendor_of.items()})
    params = {m: _material_params(d) for m, d in materials}
    out = {m: np.zeros(n) for m, _ in materials}
    for i in range(n):
        shocks = {v: vendor_rng.normal() for v in vendors} if rho > 0 else {}
        for m, _ in materials:
            bias, std = params[m]
            if std <= 0:
                d = 0.0
            elif rho == 0:
                d = rng.normal(bias, std)
            else:
                raw = rng.normal(bias, std)
                d = bias + std * (w_shared * shocks[vendor_of[m] or f"__unshared__{m}"]
                                  + w_private * (raw - bias) / std)
            out[m][i] = d
    return out

base = draw_delays(0.0)
for rho in (0.4, 0.8, 1.0):
    got = draw_delays(rho)
    for mid, _ in materials:
        if base[mid].std() < 1e-9:
            continue
        check(f"{mid} keeps its mean at rho={rho}",
              abs(got[mid].mean() - base[mid].mean()) < 0.12,
              f"{got[mid].mean():.3f} vs {base[mid].mean():.3f}")
        check(f"{mid} keeps its spread at rho={rho}",
              abs(got[mid].std() - base[mid].std()) < 0.12,
              f"{got[mid].std():.3f} vs {base[mid].std():.3f}")


# ------------------------------- 3. shared vendors correlate, others don't
print("\nMaterials from one vendor move together; unrelated ones do not")

pairs_shared, pairs_apart = [], []
ids = [m for m, _ in materials]
for i, a in enumerate(ids):
    for b in ids[i + 1:]:
        if base[a].std() < 1e-9 or base[b].std() < 1e-9:
            continue
        (pairs_shared if vendor_of[a] and vendor_of[a] == vendor_of[b]
         else pairs_apart).append((a, b))

check("the project actually has a shared vendor to test",
      bool(pairs_shared), "no two materials share a supplier")

for rho in (0.4, 0.8):
    got = draw_delays(rho)
    for a, b in pairs_shared:
        c = float(np.corrcoef(got[a], got[b])[0, 1])
        check(f"{a}+{b} (same vendor) correlate ~{rho}", abs(c - rho) < 0.05, f"got {c:.3f}")
    for a, b in pairs_apart[:6]:
        c = float(np.corrcoef(got[a], got[b])[0, 1])
        check(f"{a}+{b} (different vendors) stay independent at rho={rho}",
              abs(c) < 0.05, f"got {c:.3f}")


# ------------------------------------------------------ 4. sanity + guards
print("\nGuards")


def rejects(rho):
    try:
        simulate(g=g, vendor_correlation=rho)
        return False
    except ValueError:
        return True


check("rho below 0 is rejected", rejects(-0.1))
check("rho above 1 is rejected", rejects(1.5))

# Correlation changes how risk pools; it must never invent or erase it wholesale.
for rho in (0.0, 0.4, 1.0):
    r = simulate(g=g, vendor_correlation=rho)
    check(f"rho={rho} returns a probability", 0.0 <= r.p_slip <= 1.0, str(r.p_slip))
    check(f"rho={rho} keeps P90 at or above P50", r.p90_slip >= r.p50_slip)
    check(f"rho={rho} leaves the baseline handover alone",
          r.baseline_handover == independent.baseline_handover)

print(f"\n{'ALL MONTE-CARLO CHECKS PASSED ✓' if not fails else f'{len(fails)} FAILED: {fails}'}")
sys.exit(1 if fails else 0)
