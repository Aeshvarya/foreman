"""Foreman's morning brief — "what needs me today", before anyone asks.

Every other tool in Foreman waits to be driven: pick a material, choose a
number of days, read a graph. That is fine for a planner and useless for the
site manager who just wants to know whether today is a normal day.

This module inverts it. It walks the whole project, asks the engines the
questions a good project manager would ask on their own, and comes back with a
ranked list of sentences a non-technical person can act on:

    "Diesel generators can only slip 4 more days before the handover moves,
     and the last update was a phone call. Chase it today — a week's slip
     costs ₹16.75 lakh."

Nothing here is new intelligence. It is the risk radar, the cascade engine and
the money layer, asked on the user's behalf and phrased in plain words.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cascade import run_cascade                 # noqa: E402
from db import get_graph                        # noqa: E402
from money import cost_of_delay, fmt_inr        # noqa: E402
from risk import risk_radar                     # noqa: E402

# The "what if this goes wrong" probe. A week is the unit a supplier delay
# actually arrives in ("it'll be next week"), which makes the resulting number
# something a user recognises rather than a parameter they have to choose.
TYPICAL_SLIP_DAYS = 7

# Below this, the phrase "we're not sure" is honest.
SHAKY_CONFIDENCE = 0.8


def _how_sure(confidence: float) -> str:
    """Percentages make people nod without understanding. Words don't."""
    if confidence >= 0.9:
        return "confirmed"
    if confidence >= SHAKY_CONFIDENCE:
        return "fairly sure"
    if confidence >= 0.65:
        return "not confirmed"
    return "we're guessing"


def _urgency(slack: int | None, confidence: float) -> tuple[str, int]:
    """(status, sort weight). Tight slack is bad; being unsure about tight
    slack is worse, because you cannot even trust the slack you think you have."""
    if slack is None:
        return ("fine", 0)
    if slack <= 3:
        return ("needs you today", 4 if confidence < SHAKY_CONFIDENCE else 3)
    if slack <= 7:
        return ("needs you today" if confidence < SHAKY_CONFIDENCE else "keep an eye on it", 3)
    if confidence < SHAKY_CONFIDENCE:
        return ("worth a call", 2)
    return ("fine", 1)


def brief(project: dict | None = None) -> dict:
    """The whole morning brief in one call, so the page is one fetch."""
    g = get_graph()
    items = []

    for r in risk_radar(g):
        slack = r.breaking_point_days
        status, weight = _urgency(slack, r.confidence)

        # What a normal week-long supplier slip would actually do.
        report = run_cascade(g, r.material_id, TYPICAL_SLIP_DAYS)
        slip = report.handover_slip_days
        cost = cost_of_delay(slip, project)

        if slack is None:
            slack_text = "plenty of room — a delay here has somewhere to go"
        elif slack <= 0:
            slack_text = "no room left at all"
        elif slack == 1:
            slack_text = "1 day of room before the handover date moves"
        else:
            slack_text = f"{slack} days of room before the handover date moves"

        if slip > 0:
            risk_text = (f"If it runs a week late, handover moves {slip} day"
                         f"{'s' if slip != 1 else ''} and it costs you "
                         f"{cost['total_label']}.")
        else:
            risk_text = "Even a week late, the schedule absorbs it. Nothing to do."

        items.append({
            "id": r.material_id,
            "name": r.name,
            "supplier": r.supplier,
            "status": status,
            "weight": weight,
            "slack_days": slack,
            "slack_text": slack_text,
            "how_sure": _how_sure(r.confidence),
            "confidence": r.confidence,
            "based_on": r.confidence_source,
            "risk_text": risk_text,
            "week_slip_days": slip,
            "week_slip_cost": cost["total"],
            "week_slip_cost_label": cost["total_label"],
            "action": _action(status, r.supplier, r.name),
        })

    # Worst first; among equals, the one that costs most if it goes wrong.
    items.sort(key=lambda i: (-i["weight"], -i["week_slip_cost"]))

    urgent = [i for i in items if i["status"] == "needs you today"]
    watch = [i for i in items if i["status"] in ("keep an eye on it", "worth a call")]
    worst = items[0] if items else None

    if urgent:
        headline = (f"{len(urgent)} thing{'s' if len(urgent) != 1 else ''} "
                    f"need{'' if len(urgent) != 1 else 's'} you today")
        tone = "urgent"
    elif watch:
        headline = f"Nothing urgent — {len(watch)} worth a check"
        tone = "watch"
    else:
        headline = "Nothing is on fire today"
        tone = "calm"

    # Everything that could go wrong at once, in money. The number that makes
    # a client meeting land.
    at_stake = sum(i["week_slip_cost"] for i in items)

    return {
        "project": g.graph.get("name"),
        "handover": _handover_date(g),
        "headline": headline,
        "tone": tone,
        "subhead": _subhead(tone, urgent, watch, worst),
        "at_stake": at_stake,
        "at_stake_label": fmt_inr(at_stake),
        "counts": {"urgent": len(urgent), "watch": len(watch), "total": len(items)},
        "items": items,
    }


def _action(status: str, supplier: str, name: str) -> str:
    if status == "needs you today":
        return f"Call {supplier} today and get a firm date for the {name.split('(')[0].strip()}."
    if status == "worth a call":
        return f"Ask {supplier} to confirm in writing — we are working off an unconfirmed update."
    if status == "keep an eye on it":
        return "No action yet. Check again after the next delivery update."
    return "Nothing to do."


def _subhead(tone: str, urgent: list, watch: list, worst: dict | None) -> str:
    if tone == "urgent" and worst:
        return (f"The one that matters most is the {worst['name'].split('(')[0].strip()} "
                f"from {worst['supplier']} — {worst['slack_text']}.")
    if tone == "watch" and watch:
        return ("Nothing can break the date this week. A few suppliers owe you a "
                "confirmation, that's all.")
    return "Every material has enough room to slip without moving the handover date."


def _handover_date(g) -> str | None:
    """The date the whole project is judged on, straight from the schedule."""
    try:
        from cascade import forward_pass
        return forward_pass(g)[g.graph["handover"]].finish.isoformat()
    except Exception:
        return None


if __name__ == "__main__":
    b = brief()
    print(f"\n{b['headline'].upper()} — {b['project']}")
    print(f"{b['subhead']}\n at stake if everything slips a week: {b['at_stake_label']}\n")
    for i in b["items"]:
        print(f"  [{i['status']:>16}] {i['name'][:42]:42} {i['slack_text']}")
        print(f"                     {i['risk_text']}")
        print(f"                     → {i['action']}\n")
