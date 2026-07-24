"""Monte-Carlo schedule risk for Foreman.

The deterministic cascade answers "if X slips exactly N days, what breaks?".
Real projects aren't that certain. This models each material's arrival as a
DISTRIBUTION whose spread scales with our uncertainty about it — a delivered
material (confidence ~0.99) barely moves; an inferred one (confidence 0.6)
swings wide — then simulates thousands of futures through the same CPM engine
to answer the question a director actually asks:

    "What's the probability the handover date slips, and what's driving it?"

Outputs P(slip), the slip distribution (mean / P50 / P90), and each material's
risk contribution (correlation between its sampled delay and the handover slip).

Lightweight version of arXiv 2605.17608 (Bayesian-Monte Carlo schedule updating
for construction digital twins).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cascade import forward_pass          # noqa: E402
from db import get_graph                  # noqa: E402
from graph import MATERIAL                # noqa: E402

# How wide is "fully uncertain"? A material we know nothing about (confidence 0)
# gets this many days of standard deviation; a certain one gets ~0. Low-confidence
# materials also carry a late bias (estimates are optimistic in construction).
MAX_STD_DAYS = 12.0
LATE_BIAS_DAYS = 6.0


@dataclass
class MCResult:
    n: int
    p_slip: float                 # probability handover finishes later than baseline
    mean_slip: float
    p50_slip: float
    p90_slip: float
    baseline_handover: str
    drivers: list[dict] = field(default_factory=list)   # material risk contributions


def _material_params(node) -> tuple[float, float]:
    """(bias, std) in days for a material's arrival, from its confidence/status."""
    if node.get("shipment_status") == "delivered":
        return 0.0, 0.0
    conf = float(node.get("confidence", 0.7))
    uncertainty = 1.0 - conf
    return LATE_BIAS_DAYS * uncertainty, MAX_STD_DAYS * uncertainty


def simulate(g=None, n: int = 3000, seed: int = 7) -> MCResult:
    g = g or get_graph()
    rng = np.random.default_rng(seed)
    handover_id = g.graph["handover"]

    materials = [(mid, d) for mid, d in g.nodes(data=True) if d.get("kind") == MATERIAL]
    base_arrival = {mid: date.fromisoformat(d["expected_arrival"]) for mid, d in materials}
    params = {mid: _material_params(d) for mid, d in materials}

    baseline = forward_pass(g)[handover_id].finish

    slips = np.zeros(n)
    delays = {mid: np.zeros(n) for mid, _ in materials}
    for i in range(n):
        overrides = {}
        for mid, _ in materials:
            bias, std = params[mid]
            d_days = rng.normal(bias, std) if std > 0 else 0.0
            delays[mid][i] = d_days
            overrides[mid] = base_arrival[mid] + timedelta(days=int(round(d_days)))
        finish = forward_pass(g, overrides)[handover_id].finish
        slips[i] = (finish - baseline).days

    pos = np.clip(slips, 0, None)
    # Risk driver = correlation between a material's sampled delay and handover slip.
    drivers = []
    for mid, node in materials:
        if delays[mid].std() < 1e-6:
            corr = 0.0
        else:
            corr = float(np.corrcoef(delays[mid], slips)[0, 1])
            if np.isnan(corr):
                corr = 0.0
        drivers.append({"material": mid, "name": node["name"],
                        "risk_contribution": round(max(corr, 0.0), 3)})
    drivers.sort(key=lambda d: -d["risk_contribution"])

    return MCResult(
        n=n,
        p_slip=round(float((slips > 0).mean()), 3),
        mean_slip=round(float(pos.mean()), 2),
        p50_slip=round(float(np.percentile(pos, 50)), 1),
        p90_slip=round(float(np.percentile(pos, 90)), 1),
        baseline_handover=baseline.isoformat(),
        drivers=drivers,
    )


if __name__ == "__main__":
    r = simulate()
    print(f"Monte-Carlo schedule risk ({r.n} simulations)")
    print(f"  baseline handover : {r.baseline_handover}")
    print(f"  P(handover slips) : {r.p_slip:.0%}")
    print(f"  expected slip     : {r.mean_slip} days")
    print(f"  P50 / P90 slip    : {r.p50_slip} / {r.p90_slip} days")
    print("  top risk drivers  :")
    for d in r.drivers[:4]:
        print(f"    {d['material']} {d['name']}: contribution {d['risk_contribution']}")
