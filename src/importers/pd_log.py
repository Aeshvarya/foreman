"""P&D / procurement logs: the items, who supplies them, and when they land.

Column names differ between every customer and tracker, so each field accepts
a list of names (first match wins, case and punctuation ignored) and any field
can be pinned to an exact column. Confidence is derived from the item's status
-- a starting heuristic, labelled as such on every material it produces.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date

from .tables import read_table, text, to_date, to_num

PD_FIELDS: dict[str, list[str]] = {
    "name":     ["name", "item", "item name", "item description", "description", "material",
                 "equipment", "equipment name"],
    "vendor":   ["vendor", "vendor name", "supplier", "supplier name", "responsible contractor",
                 "subcontractor", "manufacturer"],
    "activity": ["schedule activity id reference", "p6 activity id", "activity id",
                 "schedule activity id", "p6 activity", "activity code", "linked activity",
                 "schedule activity", "activity"],
    "arrival":  ["anticipated on site date", "expected delivery date", "forecast delivery date",
                 "on site date", "expected on site", "expected arrival", "projected delivery date",
                 "forecast delivery", "delivery date", "promised date", "eta"],
    "roj":      ["required on site date", "required material available date", "required on site",
                 "roj", "p6 roj date", "roj date", "ros date", "need by date", "need by",
                 "required date"],
    "lead":     ["lead time (weeks)", "lead time weeks", "lead time"],
    "status":   ["status", "procurement status", "delivery status", "current status",
                 "submittal status"],
    "po":       ["po", "po number", "po #", "purchase order"],
}

# Status -> (confidence, shipment_status). A starting heuristic, not a measurement:
# the further an item has moved through procurement, the fewer surprises remain.
STATUS_RULES = [
    (r"deliver|on ?site|installed|received", 0.99, "delivered"),
    (r"ship|transit",                        0.90, "in_transit"),
    (r"stor",                                0.92, "delivered"),
    (r"releas|fabricat|production",          0.80, "not_shipped"),
    (r"approv",                              0.75, "not_shipped"),
    (r"revis|resubmit|reject",               0.55, "not_shipped"),
    (r"review|submitted|pending",            0.65, "not_shipped"),
]
DEFAULT_CONFIDENCE = 0.50


def _started(act: dict) -> bool:
    """Whether the schedule says this activity has already begun."""
    if act.get("_status") in ("TK_Active", "TK_Complete"):          # from an .xer
        return True
    return act.get("_rem") == 0 and act.get("duration_days", 0) > 0   # from a table


def read_pd(filename: str, data: bytes, overrides: dict[str, str] | None = None):
    return read_table(filename, data, PD_FIELDS, required=["name"], min_hits=2, overrides=overrides)


def materials_from_pd(rows: list[dict], acts: list[dict]):
    """One material per P&D row, attached to the activity it names.

    The activity is found by id, then by id without the '#n' suffix used to
    keep duplicate codes apart, then by exact activity name.
    """
    by_code = {a["id"]: a for a in acts}
    for a in acts:
        by_code.setdefault(a["id"].split("#")[0], a)
    names = Counter(a["name"].casefold() for a in acts)
    by_name = {a["name"].casefold(): a for a in acts if names[a["name"].casefold()] == 1}

    vendors: dict[str, str] = {}
    materials, stats = [], Counter()
    for r in rows:
        name = text(r.get("name"))
        if not name:
            stats["rows_without_name"] += 1
            continue
        vname = text(r.get("vendor")) or "Unknown vendor"
        sid = vendors.setdefault(vname, f"SUP-{len(vendors) + 1}")
        ref = text(r.get("activity"))
        act = by_code.get(ref) if ref else None
        if act is None and ref and ref.casefold() in by_name:
            act = by_name[ref.casefold()]
            stats["matched_by_activity_name"] += 1
        status = text(r.get("status"))
        conf, ship = DEFAULT_CONFIDENCE, "not_shipped"
        for pat, c, s in STATUS_RULES:
            if re.search(pat, status, re.I):
                conf, ship = c, s
                break
        roj, arrival = to_date(r.get("roj")), to_date(r.get("arrival"))
        if roj is None and act:
            roj = date.fromisoformat(act["early_start"])
            stats["roj_from_activity_start"] += 1
        if roj is None:
            stats["dropped_no_dates"] += 1
            continue
        if arrival is None:
            arrival = roj
            stats["arrival_assumed_roj"] += 1
        lead = to_num(r.get("lead")) or 0
        mid = f"MAT-{len(materials) + 1}"
        materials.append({
            "id": mid, "name": name[:80], "supplier": sid,
            "po": text(r.get("po")),
            "submittal_status": status.lower() or "unknown",
            "shipment_status": ship,
            "lead_time_days": int(lead * 7),
            "roj_date": roj.isoformat(), "expected_arrival": arrival.isoformat(),
            "confidence": conf,
            "confidence_source": f"derived from status '{status or 'blank'}' (heuristic, not measured)",
        })
        if act is None:
            stats["no_activity_match"] += 1
        elif _started(act):
            # the work it feeds is already under way or done: those dates are
            # history, so the item is kept on record but can't move anything
            stats["feeds_started_work"] += 1
        else:
            act["needs_materials"].append(mid)
            stats["linked_to_activity"] += 1
    suppliers = [{"id": s, "name": n, "reliability": 0.85} for n, s in vendors.items()]
    return materials, suppliers, stats
