"""The cost of waiting — what a week of doing nothing actually takes from you.

Every project tool tells you a material is late. Foreman's claim is that it
tells you *early enough to still do something cheap about it*, and this module
is where that claim gets proved instead of asserted.

The insight is physical, not rhetorical: recovery options decay with time.

  - An alternate supplier who needs 24 days is a real option today and an
    impossible one three weeks from now, because the date they must hit
    has not moved.
  - Expediting buys less the later you start: once fabrication and shipping
    are nearly done there is simply less window left to compress.
  - Site overtime is the one option that does NOT decay — which is why it is
    always the last one standing, and the most expensive.

So we walk a cursor forward a week at a time, ask the same recovery question at
each stop with only the options that would still exist then, and watch the
cheapest answer get worse until there is no answer left but the penalty.

That produces the sentence the whole product exists to earn:

    "Act today and it costs ₹1.8 lakh. Find out when the truck doesn't turn
     up and it costs ₹6.7 lakh. Foreman is telling you 11 days early."
"""

from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from alt_supplier import recommend                       # noqa: E402
from cascade import run_cascade_multi                    # noqa: E402
from db import get_graph                                 # noqa: E402
from graph import ACTIVITY, MATERIAL                     # noqa: E402
from money import cost_of_delay, fmt_inr, values         # noqa: E402
from recovery import (                                   # noqa: E402
    CRASH_CAP_DAYS, CRASH_FRACTION, EXPEDITE_CAP_DAYS, EXPEDITE_FRACTION, _short,
)

WEEKS_AHEAD = 6


def cost_of_waiting(material_id: str, delay_days: int = 7,
                    weeks: int = WEEKS_AHEAD, project: dict | None = None) -> dict:
    """Week-by-week: the cheapest way to protect the handover, and when it dies."""
    g = get_graph()
    node = g.nodes.get(material_id, {})
    if node.get("kind") != MATERIAL:
        raise ValueError(f"{material_id} is not a material")

    today = date.today()
    delays = {material_id: int(delay_days)}
    slip = run_cascade_multi(g, delays).handover_slip_days
    exposure = cost_of_delay(slip, project)

    try:
        needed_by = date.fromisoformat(node["roj_date"])
    except (KeyError, ValueError):
        needed_by = today + timedelta(days=30)
    try:
        arrives = date.fromisoformat(node["expected_arrival"])
    except (KeyError, ValueError):
        arrives = needed_by

    # The day a project WITHOUT Foreman finds out: the delivery does not turn
    # up when it was expected. Everything before that is warning we are giving.
    discovered_without_us = arrives + timedelta(days=int(delay_days))
    warning_days = max(0, (discovered_without_us - today).days)

    # Nothing breaks, so there is nothing to buy back. Saying "nothing can be
    # done" here would be alarming and wrong — they are two different zeros.
    if slip <= 0:
        return {
            "material": material_id, "name": node.get("name", material_id),
            "supplier": g.nodes[node["supplier"]]["name"] if node.get("supplier") in g.nodes else "",
            "delay_days": int(delay_days), "handover_slip_days": 0,
            "exposure": exposure, "safe": True,
            "needed_by": needed_by.isoformat(),
            "expected_arrival": arrives.isoformat(),
            "discovered_without_foreman": discovered_without_us.isoformat(),
            "warning_days": warning_days, "checkpoints": [],
            "act_now_cost": 0, "act_now_label": fmt_inr(0),
            "wait_cost": 0, "wait_label": fmt_inr(0),
            "options_expire": None,
            "headline": (f"Even {delay_days} days late, the schedule absorbs this. "
                         f"Nothing to spend and nothing to chase."),
        }

    checkpoints = []
    for w in range(weeks + 1):
        as_of = today + timedelta(days=7 * w)
        best = _best_option(g, material_id, delays, slip, as_of, needed_by, exposure, project)
        checkpoints.append({
            "week": w,
            "date": as_of.isoformat(),
            "label": "today" if w == 0 else f"in {w} week{'s' if w != 1 else ''}",
            "past_the_point": as_of > discovered_without_us,
            **best,
        })

    now, later = checkpoints[0], checkpoints[-1]

    return {
        "material": material_id,
        "name": node.get("name", material_id),
        "supplier": g.nodes[node["supplier"]]["name"] if node.get("supplier") in g.nodes else "",
        "delay_days": int(delay_days),
        "handover_slip_days": slip,
        "exposure": exposure,
        "needed_by": needed_by.isoformat(),
        "expected_arrival": arrives.isoformat(),
        "discovered_without_foreman": discovered_without_us.isoformat(),
        "warning_days": warning_days,
        "checkpoints": checkpoints,
        "act_now_cost": now["cost"],
        "act_now_label": now["cost_label"],
        "wait_cost": later["cost"],
        "wait_label": later["cost_label"],
        "options_expire": _expiry_note(checkpoints),
        "headline": _headline(now, later, warning_days, exposure),
    }


def _best_option(g, material_id, delays, base_slip, as_of, needed_by,
                 exposure, project) -> dict:
    """Cheapest way to protect the handover *given only what still exists then*."""
    rates = values(project)
    days_left = (needed_by - as_of).days
    candidates = []

    # 1. Expedite — the window you can compress shrinks as the date closes in.
    pull = _expedite_capacity(g, material_id, delays[material_id], as_of, needed_by)
    if pull > 0:
        trial = dict(delays)
        trial[material_id] = max(0, delays[material_id] - pull)
        saved = base_slip - run_cascade_multi(g, trial).handover_slip_days
        if saved > 0:
            candidates.append(_opt("expedite",
                f"Pay to speed up the {_short(g.nodes[material_id]['name'])}",
                rates["expedite_day_rate"] * pull, saved, exposure,
                f"{pull} day(s) of the delivery window can still be compressed."))

    # 2. Switch supplier — only if they can physically still make the date.
    try:
        alts = [a for a in recommend(material_id).get("alternates", [])
                if a["lead_days"] <= days_left]
    except Exception:
        alts = []
    if alts:
        alt = alts[0]
        new_arrival = as_of + timedelta(days=int(alt["lead_days"]))
        try:
            planned = date.fromisoformat(g.nodes[material_id]["expected_arrival"])
            equivalent = max(0, (new_arrival - planned).days)
        except (KeyError, ValueError):
            equivalent = 0
        if equivalent < delays[material_id]:
            trial = dict(delays)
            trial[material_id] = equivalent
            saved = base_slip - run_cascade_multi(g, trial).handover_slip_days
            if saved > 0:
                candidates.append(_opt("switch",
                    f"Order it from {alt['name']} instead",
                    rates["switching_cost"], saved, exposure,
                    f"{alt['name']} needs {alt['lead_days']} days and there are "
                    f"{days_left} left."))

    # 3. Site overtime — does not decay, and is why the last resort is dear.
    for entry in run_cascade_multi(g, delays).slipped[:2]:
        act = entry["activity"]
        n = g.nodes.get(act, {})
        if n.get("kind") != ACTIVITY:
            continue
        duration = int(n.get("duration_days", 0))
        crash = min(CRASH_CAP_DAYS, math.floor(duration * CRASH_FRACTION))
        if crash < 1:
            continue
        saved = base_slip - run_cascade_multi(g, delays, {act: duration - crash}).handover_slip_days
        if saved > 0:
            candidates.append(_opt("overtime",
                f"Work extra shifts on {_short(n.get('name', act))}",
                rates["overtime_day_rate"] * crash, saved, exposure,
                "Site overtime is still possible — it just costs more than "
                "fixing the supply would have."))
            break

    if not candidates:
        return {
            "option": None, "kind": "none",
            "cost": exposure["total"], "cost_label": exposure["total_label"],
            "days_saved": 0, "why": "Nothing can buy the date back by now. "
                                    "All that is left is paying for being late.",
        }

    # Cheapest way to fully protect the date; if none fully protects it, the
    # one that leaves the smallest total bill.
    for c in candidates:
        c["total_bill"] = c["cost"] + (base_slip - c["days_saved"]) * exposure["per_day"]
    best = min(candidates, key=lambda c: c["total_bill"])
    return {
        "option": best["title"], "kind": best["kind"],
        "cost": best["total_bill"],
        "cost_label": fmt_inr(best["total_bill"]),
        "days_saved": best["days_saved"], "why": best["why"],
    }


def _opt(kind, title, cost, days_saved, exposure, why) -> dict:
    return {"kind": kind, "title": title, "cost": cost,
            "days_saved": days_saved, "why": why}


def _expedite_capacity(g, material_id, delay_days, as_of, needed_by) -> int:
    """How many days expediting can still buy, given how much window is left.

    Early on there is fabrication and transit to compress; a week before the
    date is needed there is almost nothing left to squeeze. Linear in the
    remaining share of the window — crude, but it is stated on screen and it
    matches how expediting actually behaves.
    """
    node = g.nodes[material_id]
    lead = max(1, int(node.get("lead_time_days", 30)))
    days_left = (needed_by - as_of).days
    if days_left <= 0:
        return 0
    share = min(1.0, days_left / lead)
    return min(EXPEDITE_CAP_DAYS, math.floor(delay_days * EXPEDITE_FRACTION * share))


def _expiry_note(checkpoints: list[dict]) -> str | None:
    """The moment an option a user can see today stops being available."""
    first = checkpoints[0]["kind"]
    for c in checkpoints[1:]:
        if c["kind"] != first:
            when = c["label"].replace("in ", "")
            if c["option"] is None:
                return f"Within {when}, nothing can buy the date back."
            return (f"Within {when} the cheap fix is gone — the best left is "
                    f"\"{c['option']}\".")
    return None


def _headline(now, later, warning_days, exposure) -> str:
    if now["option"] is None:
        return "This one is already past saving — the only question left is who to tell."
    if later["option"] is None:
        return (f"Act today: {now['cost_label']}. Wait it out: {exposure['total_label']} "
                f"and no way back. You have {warning_days} days of warning.")
    extra = later["cost"] - now["cost"]
    if extra <= 0:
        return f"Fixing this costs {now['cost_label']} whenever you do it — but sooner is safer."
    return (f"Act today: {now['cost_label']}. Leave it {later['label'].replace('in ', '')}: "
            f"{later['cost_label']} — {fmt_inr(extra)} more for waiting.")


if __name__ == "__main__":
    r = cost_of_waiting("MAT-1", 8)
    print(f"\n{r['name']} — slips {r['delay_days']}d → handover +{r['handover_slip_days']}d "
          f"({r['exposure']['total_label']} at stake)")
    print(f"{r['headline']}\n")
    print(f"  without Foreman you'd find out on {r['discovered_without_foreman']} "
          f"({r['warning_days']} days from now)\n")
    for c in r["checkpoints"]:
        opt = c["option"] or "— nothing left —"
        print(f"  {c['label']:>13} ({c['date']})  {c['cost_label']:>12}   {opt}")
    if r["options_expire"]:
        print(f"\n  ⚠ {r['options_expire']}")
