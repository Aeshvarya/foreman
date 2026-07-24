"""Alternate-supplier recommender for Foreman.

When a material is at risk (its supplier is unreliable, or a delay threatens the
handover), the next question is always "who else can supply this, fast enough?"

Foreman embeds every candidate supplier as a capability vector
(reliability, speed, region proximity) and ranks market alternates in the same
category by cosine similarity to the ideal profile — favouring high reliability,
short lead time, and a nearby region. It also checks each alternate's lead time
against how many days we actually have before the material is needed.

This is the lightweight, explainable stand-in for the GNN supply-network
link-prediction line (Kosasih & Brintrup): same goal — surface hidden fallback
options on disruption — without a heavy training pipeline.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import get_graph                 # noqa: E402
from graph import MATERIAL, SUPPLIER     # noqa: E402

CATALOG = json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "market_suppliers.json").read_text()
)["categories"]

_REGIONS = ["north", "south", "east", "west", "central"]

# Map a material to a supply category by keywords in its name.
_CATEGORY_RULES = [
    ("switchgear", "electrical_switchgear"),
    ("generator", "generators"),
    ("cabling", "power_cabling"), ("cable", "power_cabling"),
    ("crac", "hvac_cooling"), ("cooling", "hvac_cooling"), ("hvac", "hvac_cooling"),
    ("steel", "structural_steel"),
    ("precast", "precast_concrete"), ("concrete", "precast_concrete"),
    ("fire", "fire_suppression"), ("novec", "fire_suppression"),
    ("busway", "busway"), ("busbar", "busway"),
]


def category_of(material_name: str) -> str | None:
    n = material_name.lower()
    for kw, cat in _CATEGORY_RULES:
        if kw in n:
            return cat
    return None


def _vec(reliability: float, lead_days: float, region: str,
         ref_region: str, max_lead: float) -> np.ndarray:
    """Capability embedding: [reliability, speed, region_proximity]."""
    speed = 1.0 - min(lead_days / max_lead, 1.0)      # shorter lead -> closer to 1
    proximity = 1.0 if region == ref_region else 0.4  # same region logistics win
    return np.array([reliability, speed, proximity], dtype=float)


def recommend(material_id: str, k: int = 2) -> dict:
    """Return ranked alternate suppliers for a material's category."""
    g = get_graph()
    if material_id not in g.nodes or g.nodes[material_id].get("kind") != MATERIAL:
        return {"material": material_id, "error": "unknown material", "alternates": []}

    mat = g.nodes[material_id]
    cat = category_of(mat["name"])
    candidates = CATALOG.get(cat, []) if cat else []

    # Current supplier context (region + how many days until ROJ).
    cur_sup_id = mat.get("supplier")
    cur_region = g.nodes[cur_sup_id].get("region", "west") if cur_sup_id in g.nodes else "west"
    cur_region = cur_region if cur_region in _REGIONS else "west"
    try:
        days_to_roj = (date.fromisoformat(mat["roj_date"]) - date.today()).days
    except Exception:
        days_to_roj = None

    if not candidates:
        return {"material": material_id, "name": mat["name"], "category": cat,
                "days_to_roj": days_to_roj, "alternates": []}

    max_lead = max(c["lead_days"] for c in candidates)
    ideal = np.array([1.0, 1.0, 1.0])   # perfectly reliable, instant, local
    scored = []
    for c in candidates:
        v = _vec(c["reliability"], c["lead_days"], c["region"], cur_region, max_lead)
        sim = float(np.dot(v, ideal) / (np.linalg.norm(v) * np.linalg.norm(ideal)))
        feasible = (days_to_roj is None) or (c["lead_days"] <= days_to_roj)
        scored.append({**c, "fit": round(sim, 3),
                       "meets_roj": feasible})
    # Rank: feasible first, then capability fit.
    scored.sort(key=lambda x: (x["meets_roj"], x["fit"]), reverse=True)

    return {"material": material_id, "name": mat["name"], "category": cat,
            "days_to_roj": days_to_roj, "alternates": scored[:k]}


if __name__ == "__main__":
    for mid in ["MAT-2", "MAT-6", "MAT-3"]:
        r = recommend(mid)
        print(f"\n{mid} — {r.get('name')}  [{r.get('category')}]  "
              f"days to ROJ: {r.get('days_to_roj')}")
        for a in r["alternates"]:
            ok = "✓ meets ROJ" if a["meets_roj"] else "✗ too slow"
            print(f"  → {a['name']} ({a['region']}) rel {a['reliability']:.0%}, "
                  f"lead {a['lead_days']}d, fit {a['fit']} · {ok}")
