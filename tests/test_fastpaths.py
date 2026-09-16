"""The closed-form shortcuts in paths.py must give the SAME answers as the full
forward pass -- not close ones.

The radar, the morning brief and Monte-Carlo moved off repeated forward passes
onto paths.handover_model. That is only allowed because the maths says the two
are identical; this file checks it on randomly generated schedules that use
every link type, negative lags, milestones, planned-start floors, several
materials per activity, shared vendors and delivered items.

Run:  python tests/test_fastpaths.py
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cascade import forward_pass, run_cascade            # noqa: E402
from graph import MATERIAL, build_graph                  # noqa: E402
from montecarlo import _material_params, simulate        # noqa: E402
from paths import handover_model                         # noqa: E402
from projects import _normalise                          # noqa: E402
from risk import MAX_PROBE_DAYS, _breaking_point_search, breaking_point   # noqa: E402

fails: list[str] = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label)
        print(f"  FAIL {label}  {detail}")


def random_project(seed: int, n_act: int) -> dict:
    rnd = random.Random(seed)
    start = date(2026, 1, 5)
    sups = [{"id": f"SUP-{i}", "name": f"Vendor {i}"} for i in range(1, rnd.randint(2, 5) + 1)]
    mats, acts = [], []
    for i in range(1, n_act + 1):
        aid = f"A{i}"
        preds = rnd.sample([a["id"] for a in acts], k=min(len(acts), rnd.randint(0, 3)))
        act = {"id": aid, "name": aid,
               "duration_days": rnd.choice([0, 1, 2, 3, 5, 8, 13]),
               "early_start": (start + timedelta(days=rnd.randint(0, 3 * i))).isoformat(),
               "depends_on": preds, "needs_materials": []}
        if preds and rnd.random() < 0.7:      # typed links on most, plain FS on the rest
            act["links"] = [{"pred": p, "type": rnd.choice(["FS", "FS", "SS", "FF", "SF"]),
                             "lag_days": rnd.randint(-5, 10)} for p in preds]
        for _ in range(rnd.choice([0, 0, 1, 1, 2])):
            mid = f"MAT-{len(mats) + 1}"
            arrive = start + timedelta(days=rnd.randint(0, 3 * i + 10))
            mats.append({"id": mid, "name": mid, "supplier": rnd.choice(sups)["id"],
                         "roj_date": arrive.isoformat(), "expected_arrival": arrive.isoformat(),
                         "confidence": rnd.choice([0.6, 0.75, 0.8, 0.95, 0.99]),
                         "shipment_status": rnd.choice(["not_shipped", "in_transit", "delivered"])})
            act["needs_materials"].append(mid)
            if rnd.random() < 0.2 and mats[:-1]:          # share an existing material too
                act["needs_materials"].append(rnd.choice(mats[:-1])["id"])
        acts.append(act)
    if not mats:
        mats.append({"id": "MAT-1", "name": "MAT-1", "supplier": sups[0]["id"],
                     "roj_date": start.isoformat(), "expected_arrival": start.isoformat()})
        acts[0]["needs_materials"].append("MAT-1")
    return {"project": {"name": f"random {seed}", "handover_milestone": acts[-1]["id"],
                        "start_date": start.isoformat()},
            "suppliers": sups, "materials": mats, "activities": acts}


def reference_simulate(g, n, seed, rho):
    """The Monte-Carlo loop as it was before the shortcut: one full forward
    pass per simulated future. The fast version must reproduce it exactly."""
    rng = np.random.default_rng(seed)
    vendor_rng = np.random.default_rng(seed + 1)
    h = g.graph["handover"]
    materials = [(m, d) for m, d in g.nodes(data=True) if d.get("kind") == MATERIAL]
    base_arrival = {m: date.fromisoformat(d["expected_arrival"]) for m, d in materials}
    params = {m: _material_params(d) for m, d in materials}
    vendor_of = {m: (d.get("supplier") or f"__unshared__{m}") for m, d in materials}
    vendors = sorted(set(vendor_of.values()))
    w_s, w_p = np.sqrt(rho), np.sqrt(1.0 - rho)
    baseline = forward_pass(g)[h].finish
    slips = np.zeros(n)
    delays = {m: np.zeros(n) for m, _ in materials}
    for i in range(n):
        shocks = {v: vendor_rng.normal() for v in vendors} if rho > 0 else {}
        over = {}
        for m, _ in materials:
            bias, std = params[m]
            if std <= 0:
                d = 0.0
            elif rho == 0:
                d = rng.normal(bias, std)
            else:
                raw = rng.normal(bias, std)
                d = bias + std * (w_s * shocks[vendor_of[m]] + w_p * (raw - bias) / std)
            delays[m][i] = d
            over[m] = base_arrival[m] + timedelta(days=int(round(d)))
        slips[i] = (forward_pass(g, over)[h].finish - baseline).days
    pos = np.clip(slips, 0, None)
    return (round(float((slips > 0).mean()), 3), round(float(pos.mean()), 2),
            round(float(np.percentile(pos, 50)), 1), round(float(np.percentile(pos, 90)), 1),
            baseline.isoformat())


graphs = [("seed project", build_graph())]
graphs += [(f"random #{s}", build_graph(_normalise(random_project(s, n))))
           for s, n in zip(range(60), [5, 8, 12, 20, 35, 60] * 10)]

print(f"Closed form vs full forward pass on {len(graphs)} schedules")
n_bp = n_slip = 0
for label, g in graphs:
    model = handover_model(g)
    h = g.graph["handover"]
    base = forward_pass(g)[h]
    check(f"{label}: baseline handover", model.base_start == base.start.toordinal()
          and model.base_start + model.handover_duration == base.finish.toordinal(),
          f"{date.fromordinal(model.base_start)} vs {base.start}")
    for m, d in g.nodes(data=True):
        if d.get("kind") != MATERIAL:
            continue
        fast, slow = breaking_point(g, m), _breaking_point_search(g, m, MAX_PROBE_DAYS)
        check(f"{label}: breaking point of {m}", fast == slow, f"fast {fast} vs search {slow}")
        n_bp += 1
        for delay in (0, 1, 3, 7, 20, 60):
            want = run_cascade(g, m, delay).handover_slip_days
            check(f"{label}: {m} +{delay}d slip", model.slip_for(m, delay) == want,
                  f"{model.slip_for(m, delay)} vs {want}")
            n_slip += 1
print(f"  {n_bp} breaking points and {n_slip} single-material slips compared")

print("\nMonte-Carlo: the vectorised run must reproduce the per-future loop")
for label, g in graphs[:1] + graphs[1:40:3]:
    for rho in (0.0, 0.4):
        want = reference_simulate(g, 400, 7, rho)
        r = simulate(g=g, n=400, seed=7, vendor_correlation=rho)
        got = (r.p_slip, r.mean_slip, r.p50_slip, r.p90_slip, r.baseline_handover)
        check(f"{label} rho={rho}", got == want, f"{got} vs {want}")

print(f"\n{'ALL FAST-PATH CHECKS PASSED ✓' if not fails else f'{len(fails)} FAILED'}")
sys.exit(1 if fails else 0)
