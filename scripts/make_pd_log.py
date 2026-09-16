"""Invent a P&D (procurement & delivery) log for a schedule that hasn't got one.

    python scripts/make_pd_log.py SCHEDULE.xer -o pd_log.csv
    python scripts/make_pd_log.py EXPORT.csv --project "Warehouse" --seed 3

Plenty of real schedules arrive without their procurement tracker -- an ETL
pull, an anonymised export, a demo instance. Foreman can still work from the
schedule's own fabricate / deliver / procure activities, but then every item's
confidence is a placeholder, so the risk ranking has nothing to rank on and
Monte-Carlo only shows how the schedule reacts to uncertainty.

This writes the tracker that's missing, in the shape trackers really have: one
row per item, its vendor, the P6 activity it feeds, required-on-site and
forecast dates, a procurement status, a PO number and a lead time.

EVERYTHING HERE IS INVENTED, and says so in the file's first line: vendors,
statuses, PO numbers and forecast dates are made up. What is NOT invented is
the skeleton -- which items exist, which activity each one feeds, and when the
schedule needs them; all of that is read from the schedule itself. Output is
deterministic for a given --seed, so a demo shows the same numbers twice.
"""
from __future__ import annotations

import argparse
import csv
import random
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from importers import ImportProblem                                   # noqa: E402
from importers.core import XER, detect_format                         # noqa: E402
from importers.names import is_delivery, item_name, lead_time_days    # noqa: E402

# Invented suppliers, grouped by trade so switchgear doesn't come from a
# plumbing merchant. Generic on purpose: a demo should never look like it is
# naming somebody's real supply chain.
TRADES = [
    (r"steel|metal|stud|frame|rebar|reinforc|joist|deck", ["Meridian Steel Co", "Ironvale Fabrication"]),
    (r"switchgear|electric|conduit|light|fire alarm|panel|generator|transformer|cable",
     ["Northline Electrical", "Kestrel Controls"]),
    (r"hvac|duct|air handl|chiller|ahu|fan|boiler", ["Palisade HVAC Systems", "Harbour Mechanical Supply"]),
    (r"plumb|pipe|piping|drain|water|pump", ["Brightwater Plumbing Supply", "Harbour Mechanical Supply"]),
    (r"precast|concrete|slab|cmu|column|grout|masonry|block", ["Castellan Precast"]),
    (r"glass|glazing|curtain wall|window|storefront", ["Summit Glass & Glazing"]),
    (r"roof|membrane|waterproof|insulation|sheathing|flashing", ["Blackford Roofing Supply"]),
    (r"millwork|door|drywall|ceiling|floor|paint|casework|carpet", ["Ridgeway Millwork"]),
]
GENERAL = ["Anchor Point Equipment", "Crestmoor Building Supply"]
HEADER = ["Item Description", "Vendor Name", "P6 Activity ID", "Required On Site Date",
          "Forecast Delivery Date", "Status", "PO Number", "Lead Time (weeks)"]


def schedule(path: Path, project: str | None):
    """(activities with links, the schedule's data date if it has one)."""
    data = path.read_bytes()
    if detect_format(path.name, data) == XER:
        from importers.xer import read_xer, schedule_from_xer, xer_projects
        tables = read_xer(data)
        pid = project or xer_projects(tables)[0]["id"]
        proj, _, acts, _, _, _ = schedule_from_xer(tables, pid, None)
        recalc = (proj.get("last_recalc_date") or "")[:10]
        return acts, (date.fromisoformat(recalc) if recalc else None)
    from importers import activity_table as at
    rows, _ = at.read_activity_table(path.name, data)
    projects = at.table_projects(rows)
    key = next((p["id"] for p in projects
                if project and (p["id"].lower().startswith(project.lower())
                                or project.lower() in p["name"].lower())), projects[0]["id"])
    acts, stats = at.schedule_from_rows(at.rows_for(rows, key))
    at.infer_links(acts, stats)
    return acts, None


def work_it_feeds(act: dict, successors: dict[str, list[dict]]) -> dict:
    """The activity that needs the item on site: the first one after the delivery.

    That's the activity a real P&D log names, and its start is the item's
    required-on-site date. A delivery nothing follows feeds itself.
    """
    after = successors.get(act["id"], [])
    return min(after, key=lambda s: (s["early_start"], s["id"])) if after else act


def vendor_for(rng: random.Random, item: str) -> str:
    for pattern, names in TRADES:
        if re.search(pattern, item, re.I):
            return rng.choice(names)
    return rng.choice(GENERAL)


def started(act: dict) -> bool:
    return act.get("_status") in ("TK_Active", "TK_Complete") or (
        act.get("_rem") == 0 and act["duration_days"] > 0)


def status_for(rng: random.Random, roj: date, slip: int, as_of: date) -> str:
    """A plausible procurement status for where this item is in its life."""
    arrival = roj + timedelta(days=slip)
    if arrival <= as_of:
        return "Delivered"
    if (roj - as_of).days <= 14:
        return rng.choice(["In transit", "In transit", "Released for fabrication", "Stored off site"])
    if (roj - as_of).days <= 60:
        return rng.choice(["Released for fabrication", "Approved", "Approved", "In transit"])
    if (roj - as_of).days <= 120:
        return rng.choice(["Approved", "Submitted for review", "Under review"])
    return rng.choice(["Submitted for review", "Under review", "Resubmit required", "Approved"])


def slip_for(rng: random.Random) -> int:
    """How late this vendor is running. Most are fine; a few are not."""
    r = rng.random()
    if r < 0.55:
        return 0
    if r < 0.75:
        return rng.randint(1, 5)
    if r < 0.88:
        return rng.randint(6, 15)
    if r < 0.94:
        return rng.randint(16, 40)
    return -rng.randint(1, 5)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("schedule", type=Path)
    ap.add_argument("-o", "--out", type=Path, help="where to write the CSV (default: <schedule>_pd_log.csv)")
    ap.add_argument("--project", help="project id or name, if the file holds several")
    ap.add_argument("--as-of", help="the date the log is written as of "
                                    "(default: the schedule's data date, else today)")
    ap.add_argument("--seed", type=int, default=7, help="same seed, same invented log")
    a = ap.parse_args()

    try:
        acts, data_date = schedule(a.schedule, a.project)
    except ImportProblem as e:
        sys.exit(f"✗ {e}")
    # statuses must agree with the schedule: an item P6 still shows as pending
    # can't already be "Delivered" just because today is later than its data date
    as_of = date.fromisoformat(a.as_of) if a.as_of else (data_date or date.today())

    successors: dict[str, list[dict]] = {}
    for act in acts:
        for dep in act["depends_on"]:
            successors.setdefault(dep, []).append(act)

    rows, seen = [], set()
    for act in sorted(acts, key=lambda x: (x["early_start"], x["id"])):
        if not is_delivery(act["name"]):
            continue
        item = item_name(act["name"])
        if item.lower() in seen:            # one row per item, not per step
            continue
        seen.add(item.lower())
        rng = random.Random(f"{a.seed}:{act['id']}")
        feeds = work_it_feeds(act, successors)
        roj = date.fromisoformat(feeds["early_start"])
        slip = slip_for(rng)
        if started(feeds):
            # the work that needs it has begun, so the item arrived: on time or
            # a little early, never "still late"
            slip = min(slip, 0)
            status = "Delivered"
        elif started(act):
            status = "In transit" if slip <= 5 else "Released for fabrication"
        else:
            status = status_for(rng, roj, slip, as_of)
        rows.append([item, vendor_for(rng, item), feeds["id"],
                     roj.isoformat(), (roj + timedelta(days=slip)).isoformat(), status,
                     f"PO-{rng.randrange(10000, 99999)}",
                     max(1, round(lead_time_days(act["name"], act["duration_days"]) / 7))])
    if not rows:
        sys.exit("✗ no fabricate / deliver / procure activities in that schedule to build a log from.")

    out = a.out or a.schedule.with_name(f"{a.schedule.stem}_pd_log.csv")
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([f"SYNTHETIC P&D log generated from {a.schedule.name} on {as_of} (seed {a.seed}) — "
                    "vendors, statuses, PO numbers and forecast dates are INVENTED; items, their "
                    "activities and required dates come from the schedule"])
        w.writerow([])
        w.writerow(HEADER)
        w.writerows(rows)

    late = [r for r in rows if r[4] > r[3]]
    worst = max(late, key=lambda r: (date.fromisoformat(r[4]) - date.fromisoformat(r[3])).days, default=None)
    print(f"\n✅ {out}  ·  {len(rows)} items")
    print(f"  running late          {len(late)}"
          + (f"   worst: {worst[0][:40]} ({worst[3]} → {worst[4]})" if worst else ""))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r[5]] = counts.get(r[5], 0) + 1
    print("  statuses              " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    print("  Everything except the items, their activities and required dates is invented.")


if __name__ == "__main__":
    main()
