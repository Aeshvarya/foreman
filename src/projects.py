"""Project storage for Foreman.

Lets users keep multiple projects and switch between them without ever touching
JSON. Each project is a file under data/projects/<id>.json; index.json tracks
the list + which one is active. On first run the existing demo project is
seeded automatically so nothing is lost.

The active project is what gets loaded into Neo4j (see backend startup).
"""

from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path

try:
    from src.graph import load_project as _load_demo
except ImportError:
    from graph import load_project as _load_demo

ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = ROOT / "data" / "projects"
INDEX = PROJECTS_DIR / "index.json"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "project"
    return f"{s}-{int(time.time()) % 100000}"


def _read_index() -> dict:
    _ensure_seed()
    return json.loads(INDEX.read_text())


def _write_index(idx: dict) -> None:
    INDEX.write_text(json.dumps(idx, indent=2))


def _ensure_seed() -> None:
    """First run: create the folder + seed the bundled demo project."""
    if INDEX.exists():
        return
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    demo = _load_demo()
    pid = "sunrise-dc-1-demo"
    (PROJECTS_DIR / f"{pid}.json").write_text(json.dumps(demo, indent=2))
    _write_index({
        "active": pid,
        "projects": [{"id": pid, "name": demo["project"]["name"],
                      "created": date.today().isoformat(), "seed": True}],
    })


# --------------------------------------------------------------- public api
def list_projects() -> list[dict]:
    idx = _read_index()
    active = idx["active"]
    return [{**p, "active": p["id"] == active} for p in idx["projects"]]


def get_active_id() -> str:
    return _read_index()["active"]


def load_project_file(pid: str) -> dict:
    return json.loads((PROJECTS_DIR / f"{pid}.json").read_text())


def get_active_project() -> dict:
    return load_project_file(get_active_id())


def set_active(pid: str) -> None:
    idx = _read_index()
    if not any(p["id"] == pid for p in idx["projects"]):
        raise ValueError(f"unknown project {pid}")
    idx["active"] = pid
    _write_index(idx)


def create_project(data: dict) -> str:
    """Validate + normalise a user-built project, save it, make it active."""
    proj = _normalise(data)
    pid = _slug(proj["project"]["name"])
    (PROJECTS_DIR / f"{pid}.json").write_text(json.dumps(proj, indent=2))
    idx = _read_index()
    idx["projects"].append({"id": pid, "name": proj["project"]["name"],
                            "created": date.today().isoformat()})
    idx["active"] = pid
    _write_index(idx)
    return pid


def delete_project(pid: str) -> None:
    idx = _read_index()
    idx["projects"] = [p for p in idx["projects"] if p["id"] != pid]
    if not idx["projects"]:
        raise ValueError("cannot delete the last project")
    if idx["active"] == pid:
        idx["active"] = idx["projects"][0]["id"]
    _write_index(idx)
    (PROJECTS_DIR / f"{pid}.json").unlink(missing_ok=True)


# --------------------------------------------------------------- normalise
def _normalise(data: dict) -> dict:
    """Fill sensible defaults so a user only has to enter the essentials.

    The frontend sends ids it already assigned (SUP-1, MAT-1, ACT-1) plus the
    fields a human would know; we backfill everything the engine needs so
    cascade / risk / montecarlo / alt-supplier all work unchanged.
    """
    start = data["project"].get("start_date") or date.today().isoformat()

    suppliers = [{
        "id": s["id"], "name": s["name"],
        "location": s.get("location", ""),
        "region": s.get("region", "west"),
        "reliability": float(s.get("reliability", 0.85)),
    } for s in data.get("suppliers", [])]

    materials = [{
        "id": m["id"], "name": m["name"], "supplier": m["supplier"],
        "po": m.get("po", ""),
        "submittal_status": m.get("submittal_status", "approved"),
        "fabrication_status": m.get("fabrication_status", "in_fabrication"),
        "shipment_status": m.get("shipment_status", "not_shipped"),
        "current_location": m.get("current_location", ""),
        "lead_time_days": int(m.get("lead_time_days", 30)),
        "roj_date": m["roj_date"],
        "expected_arrival": m["expected_arrival"],
        "confidence": float(m.get("confidence", 0.8)),
        "confidence_source": m.get("confidence_source", "user-entered"),
    } for m in data.get("materials", [])]

    activities = [{
        "id": a["id"], "name": a["name"],
        "duration_days": int(a.get("duration_days", 5)),
        "depends_on": a.get("depends_on", []),
        "needs_materials": a.get("needs_materials", []),
        # single project start; dependency + material constraints derive the
        # real earliest start, so users never enter per-activity dates.
        "early_start": a.get("early_start", start),
    } for a in data.get("activities", [])]

    # ---- integrity: no dangling references, no dependency cycles ----
    if not data["project"].get("name", "").strip():
        raise ValueError("project needs a name")
    if not suppliers or not materials or not activities:
        raise ValueError("a project needs at least one supplier, material and activity")
    sup_ids = {s["id"] for s in suppliers}
    mat_ids = {m["id"] for m in materials}
    act_ids = {a["id"] for a in activities}
    bad = [m["id"] for m in materials if m["supplier"] not in sup_ids]
    if bad:
        raise ValueError(f"materials reference unknown suppliers: {bad}")
    for a in activities:  # drop dangling / self references
        a["needs_materials"] = [m for m in a["needs_materials"] if m in mat_ids]
        a["depends_on"] = [d for d in a["depends_on"] if d in act_ids and d != a["id"]]
    if not _acyclic(activities):
        raise ValueError("activity dependencies contain a cycle — a schedule cannot loop")

    handover = data["project"].get("handover_milestone")
    if handover not in act_ids:
        handover = activities[-1]["id"]

    return {
        "project": {
            "name": data["project"]["name"].strip(),
            "description": data["project"].get("description", "User-created project."),
            "handover_milestone": handover,
            "start_date": start,
        },
        "suppliers": suppliers, "materials": materials, "activities": activities,
    }


def _acyclic(activities: list[dict]) -> bool:
    """Kahn's algorithm — True if the activity dependency graph has no cycle."""
    from collections import deque
    ids = {a["id"] for a in activities}
    deps = {a["id"]: [d for d in a["depends_on"] if d in ids] for a in activities}
    dependents: dict[str, list[str]] = {i: [] for i in ids}
    indeg = {i: 0 for i in ids}
    for i, ds in deps.items():
        for d in ds:
            dependents[d].append(i)
            indeg[i] += 1
    q = deque(i for i in ids if indeg[i] == 0)
    seen = 0
    while q:
        n = q.popleft()
        seen += 1
        for m in dependents[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    return seen == len(ids)


if __name__ == "__main__":
    _ensure_seed()
    print("projects:", [p["id"] for p in list_projects()], "· active:", get_active_id())
