"""Primavera P6 .xer exports: activities, their real relationships, and the
schedule's own delivery activities.

    activities   TASK       (id = task_code, e.g. "A1520")
    links        TASKPRED   (FS / SS / FF / SF + lag)
    handover     the latest finish milestone (TT_FinMile), unless one is named

Where the conversion has to approximate, it bends toward P6's own dates, so the
starting schedule in Foreman is the schedule P6 computed:
  * Durations are whole days from P6's dates. An activity stamped as starting
    at the minute its calendar day ends really starts next morning.
  * Lags convert hours -> working days using the successor's calendar. Where
    that, applied in calendar days, would start an activity later than P6 did
    (weekends inside a lag), the lag is trimmed to match P6's dates.
  * Level-of-effort and WBS-summary activities are dropped: they span other
    work rather than drive it, and their links would invent dependencies.
  * Links to other projects are dropped.
  * Links INTO completed activities are dropped: finished work stays at its
    actual dates, as it does in P6, even where it ran out of sequence.
  * A start-based link from an in-progress activity counts from its actual start.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from .names import COMPLETION_RE, is_delivery, item_name, lead_time_days
from .tables import ImportProblem, decode

DROP_TYPES = {"TT_LOE", "TT_WBS"}
LINK_TYPES = {"PR_FS": "FS", "PR_SS": "SS", "PR_FF": "FF", "PR_SF": "SF"}
PLACEHOLDER_CONFIDENCE = 0.80


def read_xer(data: bytes | str) -> dict[str, list[dict]]:
    """Every %T table in the file, as a list of row dicts."""
    text = data if isinstance(data, str) else decode(data)
    tables: dict[str, list[dict]] = defaultdict(list)
    table, cols = None, []
    for line in text.splitlines():
        parts = line.rstrip("\r").split("\t")
        tag = parts[0]
        if tag == "%T":
            table, cols = parts[1].strip(), []
        elif tag == "%F" and table:
            cols = parts[1:]
        elif tag == "%R" and table and cols:
            vals = parts[1:] + [""] * (len(cols) - len(parts) + 1)
            tables[table].append(dict(zip(cols, vals)))
    return tables


def xer_projects(tables: dict) -> list[dict]:
    """The projects in the file, biggest first."""
    names = {p.get("proj_id"): (p.get("proj_short_name") or p.get("proj_id"))
             for p in tables.get("PROJECT", [])}
    counts = Counter(t.get("proj_id") for t in tables.get("TASK", [])
                     if t.get("task_type") not in DROP_TYPES)
    return [{"id": pid, "name": names.get(pid, pid), "activities": n}
            for pid, n in counts.most_common()]


def _dt(s: str) -> datetime | None:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _num(s: str, default: float = 0.0) -> float:
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def schedule_from_xer(tables: dict, proj_id: str | None = None, handover_code: str | None = None):
    """-> (PROJECT row, proj_id, activities, handover id, P6 handover finish, stats)"""
    tasks_all = tables.get("TASK", [])
    if not tasks_all:
        raise ImportProblem("This .xer has no activities (no TASK table).")
    if proj_id is None:  # the project with the most activities
        proj_id = Counter(t["proj_id"] for t in tasks_all).most_common(1)[0][0]
    proj = next((p for p in tables.get("PROJECT", []) if p.get("proj_id") == proj_id), {})
    hpd = {c["clndr_id"]: (_num(c.get("day_hr_cnt"), 8.0) or 8.0) for c in tables.get("CALENDAR", [])}

    # When each calendar's working day ends, read off the schedule itself (an
    # anonymised XER can ship without its CALENDAR table). An activity that
    # "starts" at that moment -- the minute its predecessor finishes -- really
    # starts the next morning.
    ends_by_cal: dict[str, Counter] = defaultdict(Counter)
    for t in tasks_all:
        e = _dt(t.get("early_end_date"))
        if e and t.get("task_type") == "TT_Task":
            ends_by_cal[t.get("clndr_id")][e.time()] += 1
    day_end = {c: n.most_common(1)[0][0] for c, n in ends_by_cal.items()}

    stats = Counter()
    kept: dict[str, dict] = {}         # task_id -> activity
    code_seen: Counter = Counter()
    for t in tasks_all:
        if t["proj_id"] != proj_id:
            continue
        if t.get("task_type") in DROP_TYPES:
            stats["dropped_" + t["task_type"]] += 1
            continue
        code = (t.get("task_code") or t["task_id"]).strip()
        code_seen[code] += 1
        if code_seen[code] > 1:        # duplicate activity codes: keep them apart
            code = f"{code}#{t['task_id']}"
        milestone = t.get("task_type") in ("TT_Mile", "TT_FinMile")
        if t.get("status_code") == "TK_Complete":
            # keep the real start as well as the finish: a start-to-start
            # successor is anchored to when this activity began, not ended
            start = _dt(t.get("act_start_date")) or _dt(t.get("early_start_date"))
            end = _dt(t.get("act_end_date")) or _dt(t.get("early_end_date"))
            stats["complete"] += 1
        else:
            start = _dt(t.get("early_start_date")) or _dt(t.get("target_start_date"))
            end = _dt(t.get("early_end_date")) or _dt(t.get("target_end_date"))
        if start is None or end is None:
            stats["dropped_no_dates"] += 1
            continue
        # whole working days: the day it starts through the day it ends
        s_day, e_day = start.date(), end.date()
        de = day_end.get(t.get("clndr_id"))
        if not milestone and de is not None and start.time() >= de:
            s_day += timedelta(days=1)
            stats["start_at_day_end"] += 1
        dur = 0 if milestone else max(1, (e_day - s_day).days + 1)
        kept[t["task_id"]] = {
            "id": code,
            "name": (t.get("task_name") or "").strip() or code,
            "duration_days": dur,
            "early_start": s_day.isoformat(),
            "depends_on": [], "links": [], "needs_materials": [],
            "_type": t.get("task_type"), "_end": end, "_clndr": t.get("clndr_id"),
            # read by materials_from_schedule; _normalise drops them on save
            "_status": t.get("status_code"), "_wbs": t.get("wbs_id"),
            "_act": _dt(t.get("act_start_date")),
        }
    if not kept:
        raise ImportProblem(f"Project {proj_id} has no activities with dates.")

    for r in tables.get("TASKPRED", []):
        succ, pred = kept.get(r.get("task_id")), kept.get(r.get("pred_task_id"))
        in_succ = r.get("proj_id", proj_id) == proj_id
        in_pred = r.get("pred_proj_id", proj_id) == proj_id
        if not (in_succ or in_pred):     # another project's own logic: not ours to count
            continue
        if not (in_succ and in_pred):
            stats["links_cross_project"] += 1
            continue
        if succ is None or pred is None:
            stats["links_to_dropped_activity"] += 1
            continue
        if succ["_status"] == "TK_Complete":
            # finished work sits at its actual dates; crews often start before a
            # predecessor formally closes, and re-running logic over that history
            # would push it (and everything after it) past what really happened
            stats["links_into_completed"] += 1
            continue
        kind = LINK_TYPES.get(r.get("pred_type", "PR_FS"), "FS")
        lag = round(_num(r.get("lag_hr_cnt")) / hpd.get(succ["_clndr"], 8.0))
        if kind in ("SS", "SF") and pred["_act"] is not None:
            # an in-progress predecessor sits at its remaining start, but a
            # start-based link counts from when it actually began
            shift = (date.fromisoformat(pred["early_start"]) - pred["_act"].date()).days
            if shift > 0:
                lag -= shift
                stats["start_links_from_actual_start"] += 1
        # P6 placed these dates with the real calendars. Where calendar-day
        # arithmetic would demand a later start than P6 gave (a "-3 day" lag
        # across a weekend spans 5 calendar days, not 3), trust P6's dates.
        ps = date.fromisoformat(pred["early_start"])
        pf = ps + timedelta(days=pred["duration_days"])
        sd = timedelta(days=succ["duration_days"])
        anchor = {"FS": pf, "SS": ps, "FF": pf - sd, "SF": ps - sd}[kind]
        over = (anchor + timedelta(days=lag) - date.fromisoformat(succ["early_start"])).days
        if over > 0:
            lag -= over
            stats["lags_trimmed_to_p6"] += 1
        if pred["id"] not in succ["depends_on"]:
            succ["depends_on"].append(pred["id"])
            succ["links"].append({"pred": pred["id"], "type": kind, "lag_days": lag})
            stats[f"link_{kind}"] += 1
            if lag:
                stats["links_with_lag"] += 1

    acts = list(kept.values())
    if handover_code:
        if not any(a["id"] == handover_code for a in acts):
            raise ImportProblem(f"No activity with code {handover_code!r} to use as handover.")
        handover = handover_code
    else:
        # The same ladder the activity-table importer uses. The old rule was
        # "latest TT_FinMile, else the latest-finishing activity of any type",
        # and on a real export with no finish milestone that picked a PROCUREMENT
        # line ("Procure Structural Steel - Level 1") as the handover: a leaf with
        # no successors, so nothing could ever cascade into it and every verdict
        # came back "handover holds". A named completion milestone comes first,
        # then any zero-duration milestone, and a delivery/fabrication activity is
        # only ever used as the last resort.
        named = [a for a in acts if COMPLETION_RE.search(a["name"])]
        fin_mile = [a for a in acts if a["_type"] == "TT_FinMile"]
        milestones = [a for a in acts if a["_type"] in ("TT_Mile", "TT_FinMile")]
        build = [a for a in acts if not is_delivery(a["name"])]
        for pool, why in ((named, "named completion milestone"),
                          (fin_mile, "P6 finish milestone"),
                          (milestones, "latest milestone"),
                          (build, "latest non-delivery activity"),
                          (acts, "latest activity in the file")):
            if pool:
                handover = max(pool, key=lambda a: a["_end"])["id"]
                stats["_handover_why"] = why
                break
    p6_handover_finish = next((a["_end"].date() for a in acts if a["id"] == handover), None)
    for a in acts:
        for k in ("_type", "_end", "_clndr", "_act"):
            a.pop(k)
        if not a["links"]:
            a.pop("links")
    return proj, proj_id, acts, handover, p6_handover_finish, stats


def materials_from_schedule(acts: list[dict]):
    """No P&D log: use the schedule's own fabricate / deliver / procure activities.

    One material per item (the first step of its chain), gating that activity on
    its own planned start, so the baseline doesn't move and a slip enters where
    the vendor's work starts; the real links carry it from there. Finished
    activities are skipped because they can no longer slip.
    """
    first: dict[tuple[str, str], dict] = {}
    skipped = Counter()
    for a in sorted(acts, key=lambda x: (x["early_start"], x["id"])):
        if not is_delivery(a["name"]):
            continue
        if a.get("_status") == "TK_Complete":
            skipped["already_done"] += 1
            continue
        first.setdefault((item_name(a["name"]).lower(), a.get("_wbs") or ""), a)
    materials, suppliers = [], []
    for a in first.values():
        item = item_name(a["name"])
        n = len(materials) + 1
        suppliers.append({"id": f"SUP-{n}", "name": f"Vendor — {item}"[:80], "reliability": 0.85})
        materials.append({
            "id": f"MAT-{n}", "name": item[:80], "supplier": f"SUP-{n}",
            "submittal_status": "unknown",
            "fabrication_status": "in_fabrication" if a.get("_status") == "TK_Active" else "not_started",
            "shipment_status": "not_shipped",
            "lead_time_days": lead_time_days(a["name"], a["duration_days"]),
            "roj_date": a["early_start"], "expected_arrival": a["early_start"],
            "confidence": PLACEHOLDER_CONFIDENCE,
            "confidence_source": "placeholder — no P&D log, so no delivery status",
        })
        a["needs_materials"].append(f"MAT-{n}")
    return materials, suppliers, skipped
