"""Foreman cascade engine.

The core of Foreman: given "material X slips by N days", propagate that delay
through the knowledge graph using Critical Path Method (CPM) scheduling and
report exactly which activities slip, how much float absorbs, and whether the
handover date breaks.

This is real schedule math, not a mock:
  1. Forward pass computes each activity's earliest start/finish from its
     dependency network AND its material arrival constraints.
  2. A delay scenario shifts one material's arrival and re-runs the pass.
  3. The diff between baseline and scenario is the cascade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import networkx as nx

from graph import ACTIVITY, MATERIAL, build_graph


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


@dataclass
class ActivitySchedule:
    activity_id: str
    name: str
    start: date
    finish: date

    def shifted_vs(self, baseline: "ActivitySchedule") -> int:
        """Days this activity's finish slipped vs baseline."""
        return (self.finish - baseline.finish).days


@dataclass
class CascadeReport:
    delayed_material: str
    delay_days: int
    slipped: list[dict] = field(default_factory=list)
    absorbed: list[dict] = field(default_factory=list)
    handover_slip_days: int = 0
    handover_date: date | None = None
    baseline_handover: date | None = None
    confidence: float = 1.0
    confidence_source: str = ""
    mitigation: str = ""


def forward_pass(g: nx.DiGraph,
                 arrival_overrides: dict[str, date] | None = None
                 ) -> dict[str, ActivitySchedule]:
    """CPM forward pass over the activity network.

    An activity can start only when (a) all upstream activities finish and
    (b) all its materials have arrived. `arrival_overrides` lets a scenario
    shift material arrivals.
    """
    arrival_overrides = arrival_overrides or {}
    activities = [n for n, d in g.nodes(data=True) if d["kind"] == ACTIVITY]
    schedule: dict[str, ActivitySchedule] = {}

    for act_id in nx.topological_sort(g.subgraph(activities)):
        node = g.nodes[act_id]
        # Constraint 1: planned early start from the baseline schedule
        earliest = _d(node["early_start"])

        # Constraint 2: upstream activities must finish first
        for dep in node["depends_on"]:
            dep_finish = schedule[dep].finish
            if dep_finish > earliest:
                earliest = dep_finish

        # Constraint 3: materials must have arrived
        for mat_id in node["needs_materials"]:
            mat = g.nodes[mat_id]
            arrival = arrival_overrides.get(mat_id, _d(mat["expected_arrival"]))
            if arrival > earliest:
                earliest = arrival

        finish = earliest + timedelta(days=node["duration_days"])
        schedule[act_id] = ActivitySchedule(act_id, node["name"], earliest, finish)

    return schedule


def run_cascade(g: nx.DiGraph, material_id: str, delay_days: int) -> CascadeReport:
    """Answer: 'if this material slips N days, what breaks?'"""
    mat = g.nodes[material_id]
    assert mat["kind"] == MATERIAL, f"{material_id} is not a material"

    baseline = forward_pass(g)
    new_arrival = _d(mat["expected_arrival"]) + timedelta(days=delay_days)
    scenario = forward_pass(g, {material_id: new_arrival})

    handover_id = g.graph["handover"]
    report = CascadeReport(
        delayed_material=f"{material_id} — {mat['name']}",
        delay_days=delay_days,
        confidence=mat["confidence"],
        confidence_source=mat["confidence_source"],
        baseline_handover=baseline[handover_id].finish,
        handover_date=scenario[handover_id].finish,
    )
    report.handover_slip_days = (report.handover_date -
                                 report.baseline_handover).days

    # Which downstream activities slipped, which absorbed the hit via float
    for act_id in nx.descendants(g, material_id):
        if g.nodes[act_id]["kind"] != ACTIVITY:
            continue
        slip = scenario[act_id].shifted_vs(baseline[act_id])
        entry = {
            "activity": act_id,
            "name": g.nodes[act_id]["name"],
            "baseline_finish": baseline[act_id].finish.isoformat(),
            "new_finish": scenario[act_id].finish.isoformat(),
            "slip_days": slip,
        }
        (report.slipped if slip > 0 else report.absorbed).append(entry)

    report.slipped.sort(key=lambda e: -e["slip_days"])

    # Mitigation heuristic: expediting the material by the handover slip
    # amount protects the milestone; also surface schedule float found.
    if report.handover_slip_days > 0:
        report.mitigation = (
            f"Expedite {material_id} by {report.handover_slip_days} day(s) "
            f"(air-freight / partial shipment / second shift at "
            f"{g.nodes[mat['supplier']]['name']}) to protect handover. "
            f"{len(report.absorbed)} downstream activities have float and "
            f"absorb the remainder."
        )
    else:
        report.mitigation = (
            "No action needed — schedule float fully absorbs this delay. "
            "Monitor only."
        )
    return report


def format_report(r: CascadeReport) -> str:
    lines = [
        f"⚠ DELAY SCENARIO: {r.delayed_material} slips {r.delay_days} days",
        f"  (confidence {r.confidence:.0%} — {r.confidence_source})",
        "",
    ]
    if r.handover_slip_days > 0:
        lines.append(f"🔴 HANDOVER BREAKS: {r.baseline_handover} → "
                     f"{r.handover_date} (+{r.handover_slip_days} days)")
    else:
        lines.append(f"🟢 HANDOVER SAFE: stays {r.baseline_handover}")
    lines.append("")
    if r.slipped:
        lines.append(f"  {len(r.slipped)} activities slip:")
        for e in r.slipped:
            lines.append(f"   • {e['activity']} {e['name']}: "
                         f"{e['baseline_finish']} → {e['new_finish']} "
                         f"(+{e['slip_days']}d)")
    if r.absorbed:
        lines.append(f"  {len(r.absorbed)} activities absorb it (float): "
                     + ", ".join(e["activity"] for e in r.absorbed))
    lines += ["", f"🛠 MITIGATION: {r.mitigation}"]
    return "\n".join(lines)


if __name__ == "__main__":
    g = build_graph()
    # Demo: the 4000A switchgear slips 5 days
    print(format_report(run_cascade(g, "MAT-2", 5)))
    print("\n" + "=" * 70 + "\n")
    # Demo: cabling already on site — a "delay" changes nothing
    print(format_report(run_cascade(g, "MAT-4", 5)))
