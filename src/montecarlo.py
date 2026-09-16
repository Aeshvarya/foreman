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
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import get_graph                  # noqa: E402
from graph import MATERIAL                # noqa: E402
from paths import handover_model          # noqa: E402

# How wide is "fully uncertain"? A material we know nothing about (confidence 0)
# gets this many days of standard deviation; a certain one gets ~0. Low-confidence
# materials also carry a late bias (estimates are optimistic in construction).
MAX_STD_DAYS = 12.0
LATE_BIAS_DAYS = 6.0

# Materials from one vendor do not fail independently. A plant fire, a strike, a
# customs backlog — one event moves everything that vendor ships. Sampling them
# independently lets the late ones cancel the early ones, which quietly thins the
# tail: the model looks safer than the project is.
#
# So each material's draw is split into a shock its whole vendor feels and a shock
# only it feels, blended with weights sqrt(rho) and sqrt(1 - rho). Those weights
# are chosen because they leave every material's OWN mean and spread untouched —
# the individual delivery forecasts do not move, only the joint behaviour does.
# 0.0 reproduces the old independent model exactly.
VENDOR_CORRELATION = 0.4


@dataclass
class MCResult:
    n: int
    p_slip: float                 # probability handover finishes later than baseline
    mean_slip: float
    p50_slip: float
    p90_slip: float
    baseline_handover: str
    drivers: list[dict] = field(default_factory=list)   # material risk contributions
    vendor_correlation: float = 0.0   # shared-vendor correlation this run used
    # Share of still-moving materials whose confidence is a stand-in rather than a
    # status someone reported. Near 1.0 the run shows how the schedule reacts to
    # uncertainty, not a forecast -- the UI says so.
    placeholder_share: float = 0.0


def _material_params(node) -> tuple[float, float]:
    """(bias, std) in days for a material's arrival, from its confidence/status."""
    if node.get("shipment_status") == "delivered":
        return 0.0, 0.0
    conf = float(node.get("confidence", 0.7))
    uncertainty = 1.0 - conf
    return LATE_BIAS_DAYS * uncertainty, MAX_STD_DAYS * uncertainty


def simulate(g=None, n: int = 3000, seed: int = 7,
             vendor_correlation: float | None = None) -> MCResult:
    g = g or get_graph()
    rho = VENDOR_CORRELATION if vendor_correlation is None else float(vendor_correlation)
    if not 0.0 <= rho <= 1.0:
        raise ValueError(f"vendor_correlation must be between 0 and 1, got {rho}")

    rng = np.random.default_rng(seed)
    # The shared shocks are drawn from their own stream, so the per-material draws
    # below stay the same numbers in the same order as the independent model made.
    # That is what lets rho=0 reproduce the previous output exactly rather than
    # merely closely.
    vendor_rng = np.random.default_rng(seed + 1)

    materials = [(mid, d) for mid, d in g.nodes(data=True) if d.get("kind") == MATERIAL]
    params = {mid: _material_params(d) for mid, d in materials}

    # A material with no supplier recorded gets a vendor of its own, so it stays
    # independent instead of being lumped in with every other orphan.
    vendor_of = {mid: (d.get("supplier") or f"__unshared__{mid}") for mid, d in materials}
    vendors = sorted(set(vendor_of.values()))
    w_shared, w_private = np.sqrt(rho), np.sqrt(1.0 - rho)

    # Arrivals are the only thing that varies, so handover's start is a closed
    # form in them (paths.py): every future costs a max over the materials, not
    # a forward pass over the whole schedule. Same numbers, ~100x faster on a
    # real-size schedule.
    model = handover_model(g)
    baseline = date.fromordinal(model.base_start + model.handover_duration)

    mids = [mid for mid, _ in materials]
    bias = np.array([params[m][0] for m in mids], dtype=float)
    std = np.array([params[m][1] for m in mids], dtype=float)
    live = std > 0                               # delivered: nothing left to vary
    draws = np.zeros((n, len(mids)))
    if live.any():
        # Filled row by row, material by material -- the same order the
        # per-future loop drew them in, so a given seed gives the same futures.
        raw = rng.normal(bias[live], std[live], size=(n, int(live.sum())))
        if rho == 0:
            draws[:, live] = raw                 # untouched independent draws
        else:
            # One shock per vendor per simulated future, shared by everything it
            # ships. Standardise each material's own draw, blend the vendor's
            # shock into it, then put it back on the material's own scale.
            shocks = vendor_rng.normal(size=(n, len(vendors)))
            col = {v: j for j, v in enumerate(vendors)}
            vidx = np.array([col[vendor_of[m]] for m, keep in zip(mids, live) if keep])
            private = (raw - bias[live]) / std[live]
            draws[:, live] = bias[live] + std[live] * (w_shared * shocks[:, vidx]
                                                       + w_private * private)
    delays = {mid: draws[:, j] for j, mid in enumerate(mids)}

    whole_days = np.round(draws).astype(np.int64)    # half-to-even, like round()
    pos_of = {m: j for j, m in enumerate(mids)}
    cols = [pos_of[m] for m in model.materials]
    starts = model.starts(whole_days[:, cols] if cols else np.zeros((n, 0), dtype=np.int64))
    slips = (starts - model.base_start).astype(float)

    pos = np.clip(slips, 0, None)
    # Risk driver = correlation between a material's sampled delay and handover slip.
    drivers = []
    for mid, node in materials:
        if delays[mid].std() < 1e-6 or slips.std() < 1e-9:
            corr = 0.0                    # nothing varied, so nothing to correlate
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
        vendor_correlation=rho,
        placeholder_share=_placeholder_share(materials),
    )


def _placeholder_share(materials: list) -> float:
    moving = [d for _, d in materials if d.get("shipment_status") != "delivered"]
    if not moving:
        return 0.0
    stand_in = sum(1 for d in moving
                   if str(d.get("confidence_source", "")).lower().startswith("placeholder"))
    return round(stand_in / len(moving), 3)


if __name__ == "__main__":
    r = simulate()
    print(f"Monte-Carlo schedule risk ({r.n} simulations)")
    print(f"  baseline handover : {r.baseline_handover}")
    print(f"  P(handover slips) : {r.p_slip:.0%}")
    print(f"  vendor correlation: {r.vendor_correlation}")
    print(f"  expected slip     : {r.mean_slip} days")
    print(f"  P50 / P90 slip    : {r.p50_slip} / {r.p90_slip} days")
    print("  top risk drivers  :")
    for d in r.drivers[:4]:
        print(f"    {d['material']} {d['name']}: contribution {d['risk_contribution']}")
