"""Foreman risk radar.

Proactive intelligence: instead of waiting for a delay to be reported,
Foreman scans every material and asks two questions:

  1. Breaking point — how many days can this material slip before the
     handover milestone breaks? (computed by probing the cascade engine)
  2. Confidence — how sure are we about its current status?

Materials with a LOW breaking point and LOW confidence are the silent
killers: little room to slip, and we're not even sure where they stand.
Those are the vendors to chase today.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from cascade import run_cascade
from graph import MATERIAL, build_graph

MAX_PROBE_DAYS = 45


@dataclass
class MaterialRisk:
    material_id: str
    name: str
    supplier: str
    breaking_point_days: int | None   # None = never breaks within probe range
    confidence: float
    confidence_source: str
    risk_score: float
    verdict: str


def breaking_point(g: nx.DiGraph, material_id: str,
                   max_days: int = MAX_PROBE_DAYS) -> int | None:
    """Smallest delay (in days) that slips the handover; None if not found."""
    lo, hi, answer = 1, max_days, None
    # The cascade is monotonic in delay, so binary search the threshold.
    while lo <= hi:
        mid = (lo + hi) // 2
        if run_cascade(g, material_id, mid).handover_slip_days > 0:
            answer, hi = mid, mid - 1
        else:
            lo = mid + 1
    return answer


def risk_radar(g: nx.DiGraph | None = None) -> list[MaterialRisk]:
    """Rank all materials by (breaking point x confidence) risk."""
    g = g or build_graph()
    out: list[MaterialRisk] = []

    for mat_id, node in g.nodes(data=True):
        if node["kind"] != MATERIAL:
            continue
        bp = breaking_point(g, mat_id)
        conf = node["confidence"]

        # Risk: tight breaking point is dangerous; uncertainty multiplies it.
        exposure = 1.0 if bp is None else max(0.0, 1 - (bp / MAX_PROBE_DAYS))
        exposure = 0.0 if bp is None else exposure
        score = round(exposure * (1.5 - conf), 3)

        if bp is not None and bp <= 10 and conf < 0.8:
            verdict = "🔴 CHASE TODAY — tight slack + unverified status"
        elif bp is not None and bp <= 7:
            verdict = "🟠 WATCH CLOSELY — on/near critical path"
        elif bp is not None and conf < 0.75:
            verdict = "🟡 VERIFY STATUS — unconfirmed, some slack"
        else:
            verdict = "🟢 HEALTHY — slack covers current uncertainty"

        out.append(MaterialRisk(
            material_id=mat_id, name=node["name"],
            supplier=g.nodes[node["supplier"]]["name"],
            breaking_point_days=bp, confidence=conf,
            confidence_source=node["confidence_source"],
            risk_score=score, verdict=verdict,
        ))

    out.sort(key=lambda r: -r.risk_score)
    return out


if __name__ == "__main__":
    for r in risk_radar():
        bp = "never (<45d)" if r.breaking_point_days is None else f"{r.breaking_point_days}d"
        print(f"{r.verdict}\n   {r.material_id} {r.name}"
              f"\n   breaking point: {bp} · confidence {r.confidence:.0%}"
              f" ({r.confidence_source}) · risk {r.risk_score}\n")
