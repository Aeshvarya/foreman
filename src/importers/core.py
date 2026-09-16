"""One entry point for turning an uploaded schedule into a Foreman project.

    build_import(filename, data, ...)  ->  (project dict, report)

Accepts a P6 .xer, or a P6 activity table as CSV / Excel, plus an optional
P&D log. The report is what the import screen shows and what the saved
project keeps: where every part came from, what had to be approximated, a
check that Foreman's starting schedule reproduces P6's, and anything a person
should know before trusting the numbers. Nothing is saved here -- the caller
decides (projects.create_project).
"""
from __future__ import annotations

from datetime import date
from pathlib import PurePath

import networkx as nx

from . import activity_table as at
from . import xer as xr
from .pd_log import materials_from_pd, read_pd
from .tables import ImportProblem

XER, TABLE = "xer", "activity_table"
FORMAT_LABEL = {XER: "Primavera P6 export (.xer)", TABLE: "P6 activity table (CSV / Excel)"}

XER_NOTES = [
    "Links are P6's own relationships (TASKPRED), with their types and lags.",
    "Durations are whole days from P6's dates, so the starting schedule matches P6; "
    "a slip then moves in calendar days, which slightly overstates it across weekends.",
    "Lags convert from hours to working days; where that would contradict P6's dates "
    "(weekends inside a lag) the lag is trimmed to match P6.",
    "Level-of-effort and WBS-summary activities are left out: they span other work "
    "rather than drive it.",
    "Finished work stays at its actual dates; links into completed activities are ignored, as in P6.",
]
TABLE_NOTES = [
    "Links are inferred: an activity follows one that ends 0-3 days before it starts, "
    "same WBS package first.",
    "Each delivery's room before handover moves is its P6 total float, read as calendar "
    "days (conservative on 5-day calendars).",
    "Durations are whole calendar days from P6's dates; the starting schedule matches P6.",
]


def detect_format(filename: str, data: bytes) -> str:
    head = data[:4096].lstrip(b"\xef\xbb\xbf")
    name = (filename or "").lower()
    if name.endswith(".xer") or head.startswith((b"ERMHDR", b"%T\t")) or b"\n%T\t" in head:
        return XER
    if name.endswith((".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls")):
        return TABLE
    raise ImportProblem(f"{filename}: upload a P6 schedule — an .xer export, or an activity "
                        "table as CSV or Excel.")


def _choose(projects: list[dict], wanted: str | None) -> str:
    if not projects:
        raise ImportProblem("No activities found in that file.")
    if not wanted:
        return projects[0]["id"]
    w = wanted.strip().lower()
    for p in projects:
        if str(p["id"]).lower() == w:
            return p["id"]
    for p in projects:
        if str(p["id"]).lower().startswith(w) or w in str(p["name"]).lower():
            return p["id"]
    raise ImportProblem(f"No project matching {wanted!r} in that file.")


def _break_cycles(acts: list[dict]) -> int:
    """A schedule can't loop. P6 won't let one, but merged or edited exports
    occasionally do; drop the closing link of each loop rather than refuse."""
    g = nx.DiGraph()
    g.add_nodes_from(a["id"] for a in acts)
    by_id = {a["id"]: a for a in acts}
    for a in acts:
        g.add_edges_from((d, a["id"]) for d in a["depends_on"] if d in by_id)
    broken = 0
    while True:
        try:
            u, v = nx.find_cycle(g)[-1][:2]
        except nx.NetworkXNoCycle:
            return broken
        g.remove_edge(u, v)
        succ = by_id[v]
        succ["depends_on"] = [d for d in succ["depends_on"] if d != u]
        if succ.get("links"):
            succ["links"] = [ln for ln in succ["links"] if ln["pred"] != u]
        broken += 1


def build_import(filename: str, data: bytes, *, project_id: str | None = None,
                 pd_filename: str | None = None, pd_data: bytes | None = None,
                 pd_overrides: dict[str, str] | None = None, name: str | None = None,
                 handover: str | None = None) -> tuple[dict, dict]:
    fmt = detect_format(filename, data)
    notes: list[str] = []
    warnings: list[str] = []
    stem = PurePath(filename or "schedule").stem

    # ---------------------------------------------------------- schedule
    if fmt == XER:
        tables = xr.read_xer(data)
        projects = xr.xer_projects(tables)
        pid = _choose(projects, project_id)
        proj, pid, acts, h_id, p6_finish, st = xr.schedule_from_xer(tables, pid, handover)
        n_links = sum(v for k, v in st.items() if k.startswith("link_"))
        links_source = "P6 relationships (TASKPRED)"
        suggested = proj.get("proj_short_name") or stem
        notes += XER_NOTES
        if n_links == 0:
            warnings.append("This .xer has no relationships (no TASKPRED rows), so nothing can "
                            "push anything else and delays won't cascade.")
        if not tables.get("CALENDAR"):
            notes.append("No CALENDAR table in the file: lags use an 8-hour day and the working "
                         "day's end is read from the activities' own finish times.")
    else:
        rows, _labels = at.read_activity_table(filename, data)
        projects = at.table_projects(rows)
        pid = _choose(projects, project_id)
        acts, st = at.schedule_from_rows(at.rows_for(rows, pid))
        at.infer_links(acts, st)
        n_links = st["links"]
        links_source = "inferred from dates, plus P6 total float to handover"
        suggested = next((p["name"] for p in projects if p["id"] == pid), stem)
        notes += TABLE_NOTES
        warnings.append("This file has no predecessor links, so they are inferred from dates and "
                        "each delivery's room comes from P6's total float. Treat breaking points as "
                        "a conservative screen; an .xer export gives the real chain.")
        if st["duplicate_ids"]:
            warnings.append(f"{st['duplicate_ids']} activity ids appear more than once (two "
                            "versions of one schedule?); the repeats were kept apart as id#2, id#3.")
    if st["dropped_no_dates"]:
        warnings.append(f"{st['dropped_no_dates']} activities have no dates and were left out.")

    # --------------------------------------------------------- materials
    if pd_data is not None:
        pd_rows, pd_labels = read_pd(pd_filename or "p&d.csv", pd_data, pd_overrides)
        materials, suppliers, ms = materials_from_pd(pd_rows, acts)
        materials_source = f"P&D log ({pd_filename})"
        confidence_source = "from each item's status (a heuristic, labelled on every item)"
        notes.append("P&D columns used: " + ", ".join(f"{k} = '{v}'" for k, v in pd_labels.items()))
        if ms["no_activity_match"]:
            warnings.append(f"{ms['no_activity_match']} P&D items don't name an activity in this "
                            "schedule, so they can't move it. Check the activity-id column.")
        if ms["dropped_no_dates"]:
            warnings.append(f"{ms['dropped_no_dates']} P&D items have no dates and were left out.")
        if ms["feeds_started_work"]:
            notes.append(f"{ms['feeds_started_work']} P&D items feed work that has already started, "
                         "so they're kept on record but can't move the schedule.")
    else:
        if fmt == XER:
            materials, suppliers, ms = xr.materials_from_schedule(acts)
        else:
            materials, suppliers, ms = at.materials_from_rows(acts)
        materials_source = "the schedule's own fabricate / deliver / procure activities"
        confidence_source = "placeholder — no delivery status without a P&D log"
        warnings.append("No P&D log: the schedule's delivery activities stand in for P&D items, and "
                        "their confidence is a placeholder, so Monte-Carlo shows how the schedule "
                        "reacts to uncertainty, not a forecast. Add the P&D log for real numbers.")
        if ms["already_done"]:
            notes.append(f"{ms['already_done']} delivery activities are already finished and "
                         "can't slip, so they aren't tracked.")
    if not materials:
        raise ImportProblem("Nothing to track: no P&D log was given and no activity names look "
                            "like deliveries (fabricate / deliver / procure). Add the P&D log.")

    # ---------------------------------------------------------- handover
    if fmt == TABLE:
        h, why = at.pick_handover(acts, handover)
        at.float_links(acts, h, st)
        h_id, p6_finish = h["id"], h["_p6_finish"]
        if st["tighter_than_handover"]:
            warnings.append(f"{st['tighter_than_handover']} items have less float than handover — "
                            "usually an interim deadline. Their breaking points will read tighter "
                            "than real links would give.")
    broken = _break_cycles(acts)
    if broken:
        warnings.append(f"{broken} links formed a loop and were dropped; a schedule can't loop.")

    project = {"project": {"name": (name or suggested or stem).strip()[:120],
                           "handover_milestone": h_id,
                           "description": f"Imported from {filename}"
                                          + (f" + {pd_filename}" if pd_data is not None else ""),
                           "start_date": min(a["early_start"] for a in acts)},
               "suppliers": suppliers, "materials": materials, "activities": acts}

    # ------------------------------------------------ does it reproduce P6?
    from cascade import forward_pass
    from graph import build_graph
    from projects import _normalise
    norm = _normalise(project)
    g = build_graph(norm)
    no_wait = {m["id"]: date(1900, 1, 1) for m in norm["materials"]}
    plain = forward_pass(g, no_wait)
    moved = sum(1 for a in norm["activities"] if plain[a["id"]].start.isoformat() != a["early_start"])
    with_deliveries = forward_pass(g)[h_id].finish
    h_act = next(a for a in norm["activities"] if a["id"] == h_id)
    matches = moved == 0
    if not matches:
        warnings.append(f"{moved} activities start later in Foreman than in P6 before anything is "
                        "delayed. The conversion missed something; the numbers are not trustworthy.")
    push = (with_deliveries - plain[h_id].finish).days
    if push > 0:
        warnings.append(f"The P&D log's delivery dates already push handover {push} days past "
                        "P6's date. That's a finding, not an error: P6 doesn't see deliveries.")

    report = {
        "source": filename, "pd_source": pd_filename if pd_data is not None else None,
        "format": fmt, "format_label": FORMAT_LABEL[fmt],
        "projects": projects, "chosen": pid, "suggested_name": suggested,
        "counts": {"activities": len(acts), "links": n_links, "materials": len(materials),
                   "suppliers": len(suppliers)},
        "links_source": links_source, "materials_source": materials_source,
        "confidence_source": confidence_source,
        "handover": {"id": h_id, "name": h_act["name"],
                     "p6_finish": p6_finish.isoformat() if p6_finish else None,
                     "matches_p6": matches, "moved_before_any_delay": moved},
        "stats": {k: v for k, v in sorted({**st, **{f"materials_{k}": v for k, v in ms.items()}}.items())
                  if isinstance(v, int) and v},
        "notes": notes, "warnings": warnings,
        "imported": date.today().isoformat(),
    }
    project["import"] = {k: report[k] for k in ("source", "pd_source", "format_label", "counts",
                                                "links_source", "materials_source",
                                                "confidence_source", "handover", "notes",
                                                "warnings", "imported")}
    return project, report


def format_report(r: dict) -> str:
    """The report as plain text, for the command-line converters."""
    c, h = r["counts"], r["handover"]
    lines = [f"\n{r['format_label']}  ·  {r['source']}"
             + (f"  +  {r['pd_source']}" if r["pd_source"] else ""),
             f"  projects in file     " + "; ".join(f"{p['id']} ({p['name']}, {p['activities']})"
                                                   for p in r["projects"][:6]),
             f"  chosen               {r['chosen']}",
             f"  activities           {c['activities']}",
             f"  links                {c['links']}   ({r['links_source']})",
             f"  materials            {c['materials']}   ({r['materials_source']})",
             f"  handover             {h['id']}  {h['name'][:50]}  (P6 finish {h['p6_finish']})",
             f"  baseline             " + ("✓ Foreman starts every activity on its P6 date"
                                           if h["matches_p6"] else
                                           f"⚠ {h['moved_before_any_delay']} activities moved — conversion problem"),
             "  stats                " + ", ".join(f"{k}={v}" for k, v in r["stats"].items())]
    lines += [f"  · {n}" for n in r["notes"]]
    lines += [f"  ⚠ {w}" for w in r["warnings"]]
    return "\n".join(lines)
