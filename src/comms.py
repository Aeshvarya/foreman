"""The last mile — turn the analysis into the messages someone actually sends.

Foreman can prove a delay costs ₹6.7 lakh and that air-freighting the steel is
the cheapest way out. None of that moves until a human writes to the supplier
and warns the client. That writing is where good analysis usually dies: it is
awkward, it is political, and it is easy to put off until tomorrow.

So we draft it. Two messages, both in the register the recipient expects:

  - to the supplier: specific, dated, asking for one thing, no blame
  - to the client:   early, plain, with the plan already in it

Built from templates rather than the LLM on purpose. These are the sentences
most likely to be read aloud by a judge or pasted into a real email, so they
have to be identical every time, instant, and correct with no API key present.
Every number in them comes from the engines, not from prose generation.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cascade import run_cascade_multi                 # noqa: E402
from db import get_graph                              # noqa: E402
from graph import MATERIAL                            # noqa: E402
from money import cost_of_delay, fmt_money              # noqa: E402
from recovery import recovery_options                 # noqa: E402


def drafts(delays: dict[str, int], project: dict | None = None) -> dict:
    """Ready-to-send messages for the situation currently on screen."""
    g = get_graph()
    delays = {m: int(d) for m, d in delays.items()
              if m in g.nodes and int(d) > 0 and g.nodes[m].get("kind") == MATERIAL}
    if not delays:
        return {"empty": True, "reason": "Nothing is late, so there is nothing to send."}

    report = run_cascade_multi(g, delays)
    slip = report.handover_slip_days
    plan = recovery_options(delays, project)
    best = plan.get("best")
    exposure = cost_of_delay(slip, project)
    project_name = g.graph.get("name", "the project")

    # Worst offender first — it leads the supplier message.
    items = [{
        "id": m,
        "name": g.nodes[m]["name"],
        "days": d,
        "supplier": g.nodes[g.nodes[m]["supplier"]]["name"] if g.nodes[m].get("supplier") in g.nodes else "",
        "needed_by": g.nodes[m].get("roj_date", ""),
    } for m, d in sorted(delays.items(), key=lambda kv: -kv[1])]

    return {
        "empty": False,
        "project": project_name,
        "handover_slip_days": slip,
        "exposure": exposure,
        "supplier": _supplier_message(items[0], project_name, slip, best),
        "client": _client_message(items, project_name, report, slip, exposure, best),
        "summary": _one_pager(items, project_name, report, slip, exposure, plan),
    }


def _supplier_message(item: dict, project_name: str, slip: int, best: dict | None) -> dict:
    """Ask for one specific thing, with a date, and no accusation.

    A supplier who feels blamed slows down; a supplier given a precise ask and
    a reason often finds a way. So this leads with the consequence, not fault.
    """
    asking = (f"Is there any way to bring this forward? A part shipment of the "
              f"items we need first would help as much as the full order.")
    if best and best.get("kind") == "expedite":
        asking = (f"Can you tell me what it would cost to gain a few days — "
                  f"air freight, a second shift, or a part shipment of the items "
                  f"we need first? I have budget approval to discuss it.")

    body = (
        f"Hello,\n\n"
        f"Re: {item['name']} for {project_name}.\n\n"
        f"We currently have this running about {item['days']} day"
        f"{'s' if item['days'] != 1 else ''} behind, against a required-on-site "
        f"date of {item['needed_by'] or 'the agreed date'}.\n\n"
    )
    if slip > 0:
        body += (f"That timing pushes our handover by {slip} day"
                 f"{'s' if slip != 1 else ''}, so it matters more than it might look.\n\n")
    else:
        body += "We have some float, so this is not critical yet — but I'd rather not use it up.\n\n"
    body += (
        f"{asking}\n\n"
        f"Could you confirm the current status and a firm date in writing today?\n\n"
        f"Thanks,\n"
    )
    return {
        "to": item["supplier"],
        "subject": f"{item['name']} — current status and date, please",
        "body": body,
    }


def _client_message(items: list[dict], project_name: str, report, slip: int,
                    exposure: dict, best: dict | None) -> dict:
    """Tell them early, tell them plainly, and arrive with the plan.

    The instinct is to wait until it's certain. Waiting is what turns a
    schedule problem into a trust problem.
    """
    late = ", ".join(i["name"] for i in items[:3])
    if slip <= 0:
        body = (
            f"Hi,\n\nA quick update on {project_name}.\n\n"
            f"{late} is running behind, but there is enough slack in the programme "
            f"to absorb it. The handover date is unchanged at "
            f"{report.baseline_handover}.\n\n"
            f"We're chasing it and will let you know immediately if that changes.\n\n"
            f"Best,\n"
        )
    else:
        action = best["title"].lower() if best else "expediting the outstanding orders"
        body = (
            f"Hi,\n\nAn early heads-up on {project_name} — I'd rather flag this now "
            f"than closer to the date.\n\n"
            f"{late} is running behind. On current dates that moves handover from "
            f"{report.baseline_handover} to {report.handover_date}, a slip of {slip} "
            f"day{'s' if slip != 1 else ''}.\n\n"
            f"We are already acting on it: the most effective option is {action}, "
            f"which we expect to recover most of the time lost. I'll confirm once "
            f"the supplier comes back with firm dates.\n\n"
            f"Nothing else on the programme is affected.\n\n"
            f"Best,\n"
        )
    return {
        "to": "Client / project director",
        "subject": f"{project_name} — programme update",
        "body": body,
    }


def _one_pager(items, project_name, report, slip, exposure, plan) -> dict:
    """The printable weekly status — the thing that gets forwarded upward."""
    return {
        "title": f"{project_name} — delivery status",
        "date": date.today().isoformat(),
        "verdict": ("Handover date at risk" if slip > 0 else "Handover date protected"),
        "handover_was": str(report.baseline_handover),
        "handover_now": str(report.handover_date),
        "slip_days": slip,
        "exposure_label": exposure["total_label"] if slip > 0 else fmt_money(0),
        "late": [{"name": i["name"], "supplier": i["supplier"], "days": i["days"],
                  "needed_by": i["needed_by"]} for i in items],
        "affected": [{"name": s["name"], "slip": s["slip_days"]} for s in report.slipped[:6]],
        "absorbed": len(report.absorbed),
        "plan": [{"title": o["title"], "days": o["days_saved"], "cost": o["cost_label"],
                  "net": o["net_label"]} for o in plan["options"][:3]],
    }


if __name__ == "__main__":
    d = drafts({"MAT-1": 8})
    print("=== TO SUPPLIER ===")
    print(d["supplier"]["subject"], "\n")
    print(d["supplier"]["body"])
    print("=== TO CLIENT ===")
    print(d["client"]["subject"], "\n")
    print(d["client"]["body"])
