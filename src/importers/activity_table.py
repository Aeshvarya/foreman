"""P6 activity tables: one row per activity, as CSV or Excel, and no links.

This is what a database extract or a P6 activity-view export looks like: dates,
durations, float and flags, but no predecessor table. Links are therefore
inferred, and the room each delivery has comes from P6's own total float:

How links are inferred
    B gets predecessor A when A ends 0-3 calendar days before B starts
    (3 covers a weekend), preferring A in the same WBS package; outside it,
    only an A with zero free float counts, because zero free float is P6
    saying "something starts the moment I finish". Links only ever point
    from an earlier (start, id) to a later one, so no cycles are possible,
    and every inferred link is already satisfied by P6's own dates, so the
    baseline reproduces P6 exactly. What it cannot recover: SS / FF links,
    lags, and logic between activities that don't touch in time.

Why a delivery still moves handover
    The links that don't touch in time are the ones carrying float, so dates
    alone leave most deliveries as dead ends. P6's total float fills the gap:
    each material activity gets one link to handover whose lag leaves exactly
    its float as room, so a slip moves handover the way P6 itself would.
    Deliveries already finished (remaining duration 0) or without a float value
    are not turned into materials: they can't be assessed honestly.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from .names import COMPLETION_RE, is_delivery, item_name, lead_time_days
from .tables import ImportProblem, norm_key, read_table, text, to_bool, to_date, to_num

GAP_DAYS = 3            # weekend-sized gap between a finish and the next start
MAX_PREDS = 3
PLACEHOLDER_CONFIDENCE = 0.80

# Accepted column names per field, most specific first. Covers a database
# extract (activity_id, total_float, ...), P6's Excel export field names
# (task_code, ...) and its display names (Activity ID, Total Float(d), ...).
FIELDS: dict[str, list[str]] = {
    "activity_id":   ["activity_id", "activity id", "task_code", "task code", "activity code"],
    "activity_name": ["activity_name", "activity name", "task_name", "task name", "name", "description"],
    "start":         ["start", "start date", "start_date", "early start", "early_start_date",
                      "planned start", "target_start_date"],
    "finish":        ["finish", "finish date", "end_date", "end date", "early finish", "early_end_date",
                      "planned finish", "target_end_date"],
    "project_id":    ["project_id", "project id", "proj_id"],
    "project":       ["project", "project name", "project_name", "proj_short_name"],
    "type":          ["type", "activity type", "task_type"],
    "orig_dur":      ["orig_dur", "original duration d", "original duration", "target_drtn_hr_cnt",
                      "planned duration", "duration"],
    "rem_dur":       ["rem_dur", "remaining duration d", "remaining duration", "remain_drtn_hr_cnt"],
    "total_float":   ["total_float", "total float d", "total float", "total_float_hr_cnt"],
    "free_float":    ["free_float", "free float d", "free float", "free_float_hr_cnt"],
    "parent_id":     ["parent_id", "wbs_id", "wbs code", "wbs", "wbs name", "wbs path"],
    "is_active":     ["is_active", "active"],
    "is_critical":   ["is_critical", "critical"],
    "is_longest_path": ["is_longest_path", "longest path", "driving_path_flag"],
    "status":        ["status", "activity status", "status_code"],
}


def read_activity_table(filename: str, data: bytes) -> tuple[list[dict], dict[str, str]]:
    return read_table(filename, data, FIELDS, required=["activity_id", "start", "finish"], min_hits=3)


def _project_key(r: dict) -> str:
    return text(r.get("project_id")) or text(r.get("project")) or "all"


def _is_activity_row(r: dict) -> bool:
    t = norm_key(r.get("type"))
    if "wbs" in t or "level of effort" in t or t == "loe":
        return False
    return "is_active" not in r or r["is_active"] in (None, "") or to_bool(r["is_active"])


def table_projects(rows: list[dict]) -> list[dict]:
    """The projects in the table, biggest first."""
    counts: Counter = Counter()
    names: dict[str, str] = {}
    for r in rows:
        if _is_activity_row(r):
            k = _project_key(r)
            counts[k] += 1
            names.setdefault(k, text(r.get("project")) or k)
    return [{"id": k, "name": names[k], "activities": n} for k, n in counts.most_common()]


def rows_for(rows: list[dict], project_key: str) -> list[dict]:
    return [r for r in rows if _project_key(r) == project_key and _is_activity_row(r)]


def schedule_from_rows(rows: list[dict]):
    stats = Counter()
    acts: list[dict] = []
    seen: Counter = Counter()
    for r in rows:
        s, f = to_date(r.get("start")), to_date(r.get("finish"))
        if s is None or f is None:
            stats["dropped_no_dates"] += 1
            continue
        code = text(r.get("activity_id"))
        if not code:
            stats["dropped_no_id"] += 1
            continue
        seen[code] += 1
        if seen[code] > 1:               # duplicate codes would collapse into one node
            stats["duplicate_ids"] += 1
            code = f"{code}#{seen[code]}"
        orig = to_num(r.get("orig_dur"))
        rem = to_num(r.get("rem_dur"))
        if rem is None and "complete" in norm_key(r.get("status")):
            rem = 0.0
        milestone = "milestone" in norm_key(r.get("type")) or (s == f and not orig)
        acts.append({
            "id": code, "name": text(r.get("activity_name")) or code,
            "duration_days": 0 if milestone else (f - s).days + 1,
            "early_start": s.isoformat(),
            "depends_on": [], "needs_materials": [],
            "_s": s, "_wbs": text(r.get("parent_id")),
            "_ff": to_num(r.get("free_float")), "_crit": to_bool(r.get("is_critical")),
            "_lp": to_bool(r.get("is_longest_path")),
            "_tf": to_num(r.get("total_float")), "_rem": rem,
            "_p6_finish": f,
        })
    if not acts:
        raise ImportProblem("None of the rows have an activity id with start and finish dates.")
    return acts, stats


def infer_links(acts: list[dict], stats: Counter) -> None:
    ends: dict[date, list[dict]] = defaultdict(list)
    for a in acts:
        a["_e"] = a["_s"] + timedelta(days=a["duration_days"])
        ends[a["_e"]].append(a)
    for b in acts:
        cands = [a for g in range(GAP_DAYS + 1)
                 for a in ends.get(b["_s"] - timedelta(days=g), [])
                 if (a["_s"], a["id"]) < (b["_s"], b["id"])]
        same = [a for a in cands if a["_wbs"] == b["_wbs"]]
        pool = same or [a for a in cands if a["_ff"] == 0]
        if not pool:
            stats["no_pred_found"] += 1
            continue
        latest = max(a["_e"] for a in pool)        # the tightest finish drives the start
        preds = sorted((a for a in pool if a["_e"] == latest), key=lambda a: a["id"])[:MAX_PREDS]
        b["depends_on"] = [a["id"] for a in preds]
        stats["links"] += len(preds)
        stats["same_wbs" if same else "cross_wbs_zero_free_float"] += 1


def materials_from_rows(acts: list[dict]):
    """One material per physical item, gating the first activity of its delivery chain.

    A schedule often models an item as several steps (fabricate/deliver, then a
    first-delivery milestone). They become one material on the earliest step, so a
    vendor slip enters where it really starts and the links carry it on.
    """
    materials, suppliers = [], []
    skipped = Counter()
    first: dict[tuple[str, str], dict] = {}
    for a in sorted(acts, key=lambda x: (x["_s"], x["id"])):
        if not is_delivery(a["name"]):
            continue
        if a["_rem"] == 0 and a["duration_days"] > 0:   # finished: it can't slip any more
            skipped["already_done"] += 1
            continue
        if a["_tf"] is None:     # no float means no way to tell how much a slip hurts
            skipped["no_float"] += 1
            continue
        first.setdefault((item_name(a["name"]).lower(), a["_wbs"]), a)
    for a in first.values():
        item = item_name(a["name"])
        n = len(materials) + 1
        mid, sid = f"MAT-{n}", f"SUP-{n}"
        suppliers.append({"id": sid, "name": f"Vendor — {item}"[:80], "reliability": 0.85})
        materials.append({
            "id": mid, "name": item[:80], "supplier": sid,
            "submittal_status": "unknown", "shipment_status": "not_shipped",
            "lead_time_days": lead_time_days(a["name"], a["duration_days"]),
            # planned on the schedule's own date, so the baseline doesn't move
            "roj_date": a["early_start"], "expected_arrival": a["early_start"],
            "confidence": PLACEHOLDER_CONFIDENCE,
            "confidence_source": "placeholder — the schedule has no delivery status",
        })
        a["needs_materials"].append(mid)
    return materials, suppliers, skipped


def float_links(acts: list[dict], handover: dict, stats: Counter) -> None:
    """Link every activity that needs a material to handover, leaving P6's float as room.

    Dates can't rebuild the chain from a delivery to completion: those links carry
    float, which is exactly why the activities don't touch in time. P6 already
    solved it with the real logic -- total float is how far an activity can slip
    before the finish moves. A link to handover whose lag leaves that much room
    makes a slip move handover the way P6 would. Float is measured relative to
    handover's own float and read as calendar days, which is conservative when the
    activity runs on a 5-day calendar. Negative float is clamped to zero room, so
    already-late work stays in the baseline at P6's dates and reads as critical.

    Checked against a schedule that has the real links (21 items): the shortcut
    never missed a real risk, but where float is negative because of interim
    deadlines, P6's float measures room to THOSE deadlines, not to handover, and
    the shortcut reads far tighter than the truth (1 day vs 8-114 days, or safe).
    Treat its output as a conservative screen; the .xer gives the real answer.
    """
    h = handover
    h_tf = h["_tf"] or 0.0
    links = h.setdefault("links", [{"pred": d, "type": "FS", "lag_days": 0} for d in h["depends_on"]])
    for a in acts:
        if not a["needs_materials"] or a is h or a["id"] in h["depends_on"]:
            continue
        if a["_tf"] is None or (a["_s"], a["id"]) >= (h["_s"], h["id"]):
            stats["no_float_link"] += 1
            continue
        room = max(0, round(a["_tf"] - h_tf))
        h["depends_on"].append(a["id"])
        links.append({"pred": a["id"], "type": "FS", "lag_days": (h["_s"] - a["_e"]).days - room})
        stats["float_links"] += 1
        stats["zero_room"] += room == 0
    stats["tighter_than_handover"] = sum(
        1 for a in acts if a["needs_materials"] and a["_tf"] is not None and a["_tf"] < h_tf)


def pick_handover(acts: list[dict], wanted: str | None = None) -> tuple[dict, str]:
    """A named activity, else a completion milestone, else the end of P6's
    longest path, else the last milestone."""
    if wanted:
        for a in acts:
            if a["id"] == wanted:
                return a, "chosen"
        raise ImportProblem(f"No activity with id {wanted!r} to use as handover.")
    for pool, why in (([x for x in acts if COMPLETION_RE.search(x["name"])], "completion milestone"),
                      ([x for x in acts if x["_lp"]], "end of P6 longest path"),
                      ([x for x in acts if x["duration_days"] == 0] or acts, "latest milestone")):
        if pool:
            last = max(x["_e"] for x in pool)
            return sorted((x for x in pool if x["_e"] == last), key=lambda x: x["id"])[-1], why
    raise ImportProblem("No activities to choose a handover from.")
