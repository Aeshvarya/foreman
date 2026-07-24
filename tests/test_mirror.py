"""Regression guard: the Neo4j-mirrored graph must produce IDENTICAL CPM
cascade + risk-radar results to the Stage-1 JSON-built graph. If this passes,
swapping NetworkX -> Neo4j changed nothing the engine can see.

Run:  python tests/test_mirror.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cascade import run_cascade          # noqa: E402
from db import graph_from_neo4j          # noqa: E402
from graph import build_graph            # noqa: E402
from risk import risk_radar              # noqa: E402

json_g = build_graph()
neo_g = graph_from_neo4j()

print(f"nodes  json={json_g.number_of_nodes()}  neo4j={neo_g.number_of_nodes()}")
print(f"edges  json={json_g.number_of_edges()}  neo4j={neo_g.number_of_edges()}")
assert json_g.graph["handover"] == neo_g.graph["handover"], "handover mismatch"

# Cascade parity across every material + a couple of delay sizes.
mats = [n for n, d in json_g.nodes(data=True) if d["kind"] == "material"]
for m in mats:
    for days in (3, 7, 15):
        a = run_cascade(json_g, m, days)
        b = run_cascade(neo_g, m, days)
        assert a.handover_slip_days == b.handover_slip_days, f"{m}+{days} handover"
        assert [x["activity"] for x in a.slipped] == [x["activity"] for x in b.slipped], \
            f"{m}+{days} slipped set"
print(f"cascade parity: OK across {len(mats)} materials x 3 delays")

# Risk radar parity.
ra = {r.material_id: (r.breaking_point_days, r.verdict) for r in risk_radar(json_g)}
rb = {r.material_id: (r.breaking_point_days, r.verdict) for r in risk_radar(neo_g)}
assert ra == rb, "risk radar mismatch"
print(f"risk-radar parity: OK across {len(ra)} materials")

# Show one real cascade so we SEE it working, not just assert.
r = run_cascade(neo_g, "MAT-2", 5)
print(f"\nsample (Neo4j graph): MAT-2 slips 5d -> handover slip "
      f"{r.handover_slip_days}d, {len(r.slipped)} activities slip, "
      f"confidence {r.confidence:.0%}")
print("ALL PARITY CHECKS PASSED ✓")
