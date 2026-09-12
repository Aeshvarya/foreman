"""Turn a Primavera P6 schedule (.xer) and a P&D log (.csv) into a Foreman project.

    python scripts/xer_to_foreman.py SCHEDULE.xer --pd PD_LOG.csv --name "My Project"
    python scripts/xer_to_foreman.py SCHEDULE.xer --dry-run          # schedule stats only

What comes from where
    activities   XER  TASK       (id = task_code, e.g. "A1520")
    links        XER  TASKPRED   (FS / SS / FF / SF + lag)
    handover     XER  the latest finish milestone (TT_FinMile), or --handover
    materials    P&D log rows    (one Foreman material per P&D item)
    suppliers    P&D log vendor column
    confidence   derived from each item's status — a HEURISTIC, flagged as such

Honest approximations (printed in the summary every run):
  * Durations become calendar days measured from P6's own early dates, so the
    baseline reproduces P6. Slips then propagate in calendar days, which slightly
    overstates them across weekends.
  * Lags are converted hours -> working days using the successor's calendar.
  * Level-of-effort and WBS-summary activities are dropped: they span other work
    rather than drive it, and their links would invent dependencies.
  * Links to activities in other projects are dropped.
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DROP_TYPES = {"TT_LOE", "TT_WBS"}
LINK_TYPES = {"PR_FS": "FS", "PR_SS": "SS", "PR_FF": "FF", "PR_SF": "SF"}

# P&D log column names differ between customers; first match wins (case-insensitive).
PD_COLUMNS = {
    "name":     ["name", "item", "item name", "description", "equipment"],
    "vendor":   ["vendor", "supplier", "responsible contractor", "manufacturer"],
    "activity": ["schedule activity id reference", "activity id", "p6 activity id",
                 "schedule activity id", "activity"],
    "arrival":  ["anticipated on site date", "expected delivery date", "on site date",
                 "expected arrival", "projected delivery date"],
    "roj":      ["required on site date", "required material available date", "roj",
                 "p6 roj date", "roj date"],
    "lead":     ["lead time (weeks)", "lead time", "lead time weeks"],
    "status":   ["status", "procurement status", "delivery status", "submittal status"],
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


# ------------------------------------------------------------------ XER
def read_xer(path: Path) -> dict[str, list[dict]]:
    """Every %T table in the file, as a list of row dicts."""
    raw = path.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
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


def schedule_from_xer(tables: dict, proj_id: str | None, handover_code: str | None):
    tasks_all = tables.get("TASK", [])
    if not tasks_all:
        raise SystemExit("XER has no TASK rows")
    if proj_id is None:  # the project with the most activities
        proj_id = Counter(t["proj_id"] for t in tasks_all).most_common(1)[0][0]
    proj = next((p for p in tables.get("PROJECT", []) if p.get("proj_id") == proj_id), {})
    hpd = {c["clndr_id"]: (_num(c.get("day_hr_cnt"), 8.0) or 8.0) for c in tables.get("CALENDAR", [])}

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
        dur = 0 if milestone else max(1, math.ceil((end - start).total_seconds() / 86400))
        kept[t["task_id"]] = {
            "id": code,
            "name": (t.get("task_name") or "").strip() or code,
            "duration_days": dur,
            "early_start": start.date().isoformat(),
            "depends_on": [], "links": [], "needs_materials": [],
            "_type": t.get("task_type"), "_end": end, "_clndr": t.get("clndr_id"),
        }

    for r in tables.get("TASKPRED", []):
        succ, pred = kept.get(r.get("task_id")), kept.get(r.get("pred_task_id"))
        if r.get("pred_proj_id", proj_id) != proj_id or r.get("proj_id", proj_id) != proj_id:
            stats["links_cross_project"] += 1
            continue
        if succ is None or pred is None:
            stats["links_to_dropped_activity"] += 1
            continue
        kind = LINK_TYPES.get(r.get("pred_type", "PR_FS"), "FS")
        lag = round(_num(r.get("lag_hr_cnt")) / hpd.get(succ["_clndr"], 8.0))
        if pred["id"] not in succ["depends_on"]:
            succ["depends_on"].append(pred["id"])
            succ["links"].append({"pred": pred["id"], "type": kind, "lag_days": lag})
            stats[f"link_{kind}"] += 1
            if lag:
                stats["links_with_lag"] += 1

    acts = list(kept.values())
    if handover_code:
        handover = handover_code
    else:
        fin = [a for a in acts if a["_type"] == "TT_FinMile"] or acts
        handover = max(fin, key=lambda a: a["_end"])["id"]
    p6_handover_finish = next((a["_end"].date() for a in acts if a["id"] == handover), None)
    for a in acts:
        for k in ("_type", "_end", "_clndr"):
            a.pop(k)
        if not a["links"]:
            a.pop("links")
    return proj, proj_id, acts, handover, p6_handover_finish, stats


# ------------------------------------------------------------------ P&D log
def _pick(header: list[str], wanted: list[str]) -> str | None:
    low = {h.strip().lower(): h for h in header}
    return next((low[w] for w in wanted if w in low), None)


def _date(s: str) -> date | None:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%b %d, %Y", "%d %b %Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def materials_from_pd(path: Path, acts: list[dict], overrides: dict[str, str]):
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8-sig")))
    if not rows:
        raise SystemExit(f"{path} has no rows")
    header = list(rows[0].keys())
    col = {k: overrides.get(k) or _pick(header, v) for k, v in PD_COLUMNS.items()}
    if not col["name"]:
        raise SystemExit(f"can't find an item-name column in {header}; pass --map name=<column>")

    by_code = {a["id"]: a for a in acts}
    # also accept a code that lost its "#task_id" disambiguation suffix
    for a in acts:
        by_code.setdefault(a["id"].split("#")[0], a)
    vendors: dict[str, str] = {}
    materials, stats = [], Counter()
    for i, r in enumerate(rows, 1):
        name = (r.get(col["name"]) or "").strip()
        if not name:
            stats["rows_without_name"] += 1
            continue
        vname = (r.get(col["vendor"]) or "").strip() if col["vendor"] else ""
        vname = vname or "Unknown vendor"
        sid = vendors.setdefault(vname, f"SUP-{len(vendors) + 1}")
        act = by_code.get((r.get(col["activity"]) or "").strip()) if col["activity"] else None
        status = (r.get(col["status"]) or "").strip() if col["status"] else ""
        conf, ship = DEFAULT_CONFIDENCE, "not_shipped"
        for pat, c, s in STATUS_RULES:
            if re.search(pat, status, re.I):
                conf, ship = c, s
                break
        roj = _date(r.get(col["roj"])) if col["roj"] else None
        arrival = _date(r.get(col["arrival"])) if col["arrival"] else None
        if roj is None and act:
            roj = date.fromisoformat(act["early_start"])
            stats["roj_from_activity_start"] += 1
        if roj is None:
            stats["dropped_no_dates"] += 1
            continue
        if arrival is None:
            arrival = roj
            stats["arrival_assumed_roj"] += 1
        lead = _num(r.get(col["lead"]), 0) if col["lead"] else 0
        mid = f"MAT-{len(materials) + 1}"
        materials.append({
            "id": mid, "name": name, "supplier": sid,
            "po": (r.get(col["po"]) or "").strip() if col["po"] else "",
            "submittal_status": status.lower() or "unknown",
            "shipment_status": ship,
            "lead_time_days": int(lead * 7),
            "roj_date": roj.isoformat(), "expected_arrival": arrival.isoformat(),
            "confidence": conf,
            "confidence_source": f"derived from status '{status or 'blank'}' (heuristic, not measured)",
        })
        if act:
            act["needs_materials"].append(mid)
            stats["linked_to_activity"] += 1
        else:
            stats["no_activity_match"] += 1
    suppliers = [{"id": s, "name": n, "reliability": 0.85} for n, s in vendors.items()]
    return materials, suppliers, col, stats


# ------------------------------------------------------------------ main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xer", type=Path)
    ap.add_argument("--pd", type=Path, help="P&D / procurement log exported as CSV")
    ap.add_argument("--name", help="project name in Foreman")
    ap.add_argument("--proj-id", help="XER proj_id, if the file holds several projects")
    ap.add_argument("--handover", help="activity code to treat as handover")
    ap.add_argument("--map", action="append", default=[], metavar="FIELD=Column",
                    help="override a P&D column, e.g. --map arrival='Promised Date'")
    ap.add_argument("--dry-run", action="store_true", help="print stats, save nothing")
    a = ap.parse_args()

    proj, pid, acts, handover, p6_finish, s = schedule_from_xer(read_xer(a.xer), a.proj_id, a.handover)
    name = a.name or proj.get("proj_short_name") or a.xer.stem
    print(f"\nXER  {a.xer.name}  ·  project {pid} ({proj.get('proj_short_name', '?')})")
    print(f"  activities kept      {len(acts)}   (complete: {s['complete']})")
    for k in sorted(s):
        if k.startswith("dropped_"):
            print(f"  {k:<20} {s[k]}")
    n_links = sum(v for k, v in s.items() if k.startswith("link_"))
    print(f"  links                {n_links}   " + "  ".join(f"{k[5:]}:{v}" for k, v in sorted(s.items()) if k.startswith("link_")))
    print(f"  links with lag       {s['links_with_lag']}")
    for k in ("links_cross_project", "links_to_dropped_activity"):
        if s[k]:
            print(f"  {k:<20} {s[k]}  (dropped)")
    print(f"  handover             {handover}  (P6 early finish {p6_finish})")
    if n_links == 0:
        print("  ⚠ no TASKPRED links — every activity is independent, so nothing can cascade.")

    if a.pd is None:
        if not a.dry_run:
            print("\n  (no --pd given: a Foreman project needs materials, so nothing saved)")
        return
    overrides = dict(m.split("=", 1) for m in a.map)
    materials, suppliers, col, ms = materials_from_pd(a.pd, acts, overrides)
    print(f"\nP&D  {a.pd.name}")
    print("  columns used         " + ", ".join(f"{k}={v!r}" for k, v in col.items() if v))
    missing = [k for k, v in col.items() if not v]
    if missing:
        print(f"  columns NOT found    {missing}  (use --map FIELD=Column)")
    print(f"  materials            {len(materials)}   suppliers {len(suppliers)}")
    for k in sorted(ms):
        print(f"  {k:<20} {ms[k]}")
    if ms["no_activity_match"]:
        print("  ⚠ unmatched items can't cascade — check the activity-reference column")

    project = {"project": {"name": name, "handover_milestone": handover,
                           "description": f"Imported from {a.xer.name}"
                                          + (f" + {a.pd.name}" if a.pd else ""),
                           "start_date": min(x["early_start"] for x in acts)},
               "suppliers": suppliers, "materials": materials, "activities": acts}

    from graph import build_graph
    from cascade import forward_pass
    from projects import _normalise, create_project
    norm = _normalise(project)
    g = build_graph(norm)
    hid = norm["project"]["handover_milestone"]
    # 1) schedule logic only — every material treated as already on site.
    #    This must reproduce P6; if it doesn't, the conversion is wrong.
    no_mat = {m["id"]: date(1900, 1, 1) for m in norm["materials"]}
    sched_only = forward_pass(g, no_mat)[hid].finish
    ok = "✓ matches P6" if sched_only == p6_finish else f"⚠ P6 says {p6_finish} — conversion problem"
    print(f"\nHandover, schedule logic only:     {sched_only}  {ok}")
    # 2) with the P&D log's anticipated delivery dates — what P6 cannot see.
    fin = forward_pass(g)[hid].finish
    gap = (fin - sched_only).days
    note = (f"deliveries already push handover {gap} day(s) past P6" if gap > 0
            else "deliveries don't move handover")
    print(f"Handover, with P&D delivery dates: {fin}  ({note})")
    print("Approximations: calendar-day slips · lags in working days · LOE/WBS dropped · "
          "confidence from status (heuristic)")
    if a.dry_run:
        print("(dry run — nothing saved)")
        return
    new_id = create_project(project)
    print(f"\n✅ saved as project '{new_id}' and made active — reload Foreman")


if __name__ == "__main__":
    main()
