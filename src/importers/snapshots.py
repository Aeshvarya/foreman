"""Schedule snapshots: every activity as P6 last computed it, for comparing updates.

A snapshot is one version of one project -- each activity's start, finish and
total float, plus the milestone the project is judged on. Comparing two answers
what a scheduler asks every week (what moved, what lost float, did completion
slip?) straight from P6's own numbers, with none of the modelling an import does.

One file can hold several snapshots: an .xer with more than one project, or a
database extract that keeps the previous upload's rows beside the current ones.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from . import activity_table as at
from . import xer as xr
from .core import XER, detect_format
from .names import COMPLETION_RE
from .tables import ImportProblem, norm_key, text, to_bool, to_date, to_num


@dataclass
class Activity:
    name: str
    start: date
    finish: date
    float_days: float | None
    done: bool
    milestone: bool


@dataclass
class Snapshot:
    key: str
    label: str
    group: str                    # the project this is a version of
    current: bool                 # False for rows kept from an earlier upload
    data_date: str | None = None
    activities: dict[str, Activity] = field(default_factory=dict)

    def finish_milestone(self) -> str | None:
        """The activity the project is judged on: a named completion milestone,
        else the last milestone, else the last activity."""
        acts = self.activities
        pool = ([k for k, a in acts.items() if COMPLETION_RE.search(a.name)]
                or [k for k, a in acts.items() if a.milestone] or list(acts))
        return max(pool, key=lambda k: (acts[k].finish, k)) if pool else None

    def summary(self) -> dict:
        return {"key": self.key, "label": self.label, "activities": len(self.activities),
                "current": self.current, "data_date": self.data_date}


def xer_snapshots(data: bytes) -> list[Snapshot]:
    tables = xr.read_xer(data)
    hpd = {c["clndr_id"]: (to_num(c.get("day_hr_cnt")) or 8.0) for c in tables.get("CALENDAR", [])}
    projects = {p.get("proj_id"): p for p in tables.get("PROJECT", [])}
    snaps: dict[str, Snapshot] = {}
    for t in tables.get("TASK", []):
        if t.get("task_type") in xr.DROP_TYPES:
            continue
        pid = t.get("proj_id")
        if pid not in snaps:
            p = projects.get(pid, {})
            snaps[pid] = Snapshot(key=str(pid), label=p.get("proj_short_name") or str(pid), group=str(pid),
                                  current=True, data_date=(p.get("last_recalc_date") or "")[:10] or None)
        done = t.get("status_code") == "TK_Complete"
        start = xr._dt(t.get("act_start_date")) or xr._dt(t.get("early_start_date")) or xr._dt(t.get("target_start_date"))
        finish = ((xr._dt(t.get("act_end_date")) if done else None)
                  or xr._dt(t.get("early_end_date")) or xr._dt(t.get("target_end_date")))
        if start is None or finish is None:
            continue
        tf = to_num(t.get("total_float_hr_cnt"))
        code = (t.get("task_code") or t["task_id"]).strip()
        snaps[pid].activities[code] = Activity(
            name=(t.get("task_name") or code).strip(), start=start.date(), finish=finish.date(),
            float_days=None if tf is None else round(tf / hpd.get(t.get("clndr_id"), 8.0), 1),
            done=done, milestone=t.get("task_type") in ("TT_Mile", "TT_FinMile"))
    return list(snaps.values())


def table_snapshots(filename: str, data: bytes) -> list[Snapshot]:
    rows, _ = at.read_activity_table(filename, data)
    snaps: dict[str, Snapshot] = {}
    for r in rows:
        kind = norm_key(r.get("type"))
        if "wbs" in kind or "level of effort" in kind or kind == "loe":
            continue
        pid = text(r.get("project_id")) or text(r.get("project")) or "all"
        label = text(r.get("project")) or pid
        key = f"{pid}|{label}"
        current = "is_active" not in r or r["is_active"] in (None, "") or to_bool(r["is_active"])
        snap = snaps.setdefault(key, Snapshot(key=key, label=label, group=pid, current=False))
        snap.current = snap.current or current
        start, finish, code = to_date(r.get("start")), to_date(r.get("finish")), text(r.get("activity_id"))
        if start is None or finish is None or not code:
            continue
        orig, rem = to_num(r.get("orig_dur")), to_num(r.get("rem_dur"))
        milestone = "milestone" in kind or (start == finish and not orig)
        done = "complete" in norm_key(r.get("status")) or (rem == 0 and not milestone)
        snap.activities[code] = Activity(name=text(r.get("activity_name")) or code, start=start,
                                         finish=finish, float_days=to_num(r.get("total_float")),
                                         done=done, milestone=milestone)
    return list(snaps.values())


def snapshots(filename: str, data: bytes) -> list[Snapshot]:
    """Every project version in the file, biggest first."""
    snaps = xer_snapshots(data) if detect_format(filename, data) == XER else table_snapshots(filename, data)
    snaps = [s for s in snaps if s.activities]
    if not snaps:
        raise ImportProblem(f"{filename}: no activities with dates in it.")
    return sorted(snaps, key=lambda s: -len(s.activities))


def pick_pair(older: list[Snapshot], newer: list[Snapshot], older_key: str | None,
              newer_key: str | None, same_file: bool) -> tuple[Snapshot, Snapshot]:
    """The two versions to compare: the ones asked for, else the obvious pair."""
    def find(snaps: list[Snapshot], key: str) -> Snapshot:
        for s in snaps:
            if s.key == key:
                return s
        raise ImportProblem(f"No version {key!r} in that file.")

    o = find(older, older_key) if older_key else None
    n = find(newer, newer_key) if newer_key else None
    if same_file and (o is None or n is None):
        groups: dict[str, list[Snapshot]] = defaultdict(list)
        for s in older:
            groups[s.group].append(s)
        pair = next((g for g in groups.values() if len(g) >= 2), None)
        if pair is None:
            raise ImportProblem("That file holds one version of each project — add the other "
                                "update as a second file to compare them.")
        pair.sort(key=lambda s: (s.current, s.data_date or "", s.label))
        o, n = o or pair[0], n or pair[-1]
    else:
        o = o or older[0]
        n = n or next((s for s in newer if s.group == o.group or s.label == o.label), newer[0])
    if o is n:
        raise ImportProblem("Pick two different versions to compare.")
    return o, n
