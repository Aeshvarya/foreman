"""Foreman API — FastAPI layer over the reasoning brain.

Thin wrappers around the already-built + tested brain modules (nothing in
`src/` changes). The premium web frontend (../web) calls these endpoints.

Run:  uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Make src/ importable so the brain modules' bare imports resolve.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import time

from db import get_graph, load_to_neo4j_if_enabled, neo4j_enabled   # noqa: E402
from cascade import run_cascade, run_cascade_multi   # noqa: E402
from risk import risk_radar                    # noqa: E402
from montecarlo import simulate                # noqa: E402
from alt_supplier import recommend             # noqa: E402
from agents.brain import answer as brain_answer          # noqa: E402
import money                                             # noqa: E402
from recovery import recovery_options                    # noqa: E402
from agents.kg_builder import (                          # noqa: E402
    build_graph_from_docs, list_docs, save_uploaded_doc, reset_docs,
)
from graph import MATERIAL, SUPPLIER, ACTIVITY           # noqa: E402
import projects                                          # noqa: E402

app = FastAPI(title="Foreman API", version="2.0")

# Same-origin in production (FastAPI serves the built SPA), so this list only
# matters for the split dev setup — and for anyone pointing a hosted frontend
# at this API. Never hardcoded again: ALLOWED_ORIGINS is comma-separated.
_ORIGINS = [
    o.strip() for o in
    os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGINS,
    allow_methods=["*"], allow_headers=["*"],
)


def _load_active_into_neo4j(retries: int = 8) -> None:
    """Push the active project into Neo4j (retry while Neo4j warms up)."""
    if not neo4j_enabled():
        print("[startup] no NEO4J_URI — running on the JSON mirror")
        return
    for i in range(retries):
        try:
            load_to_neo4j_if_enabled(projects.get_active_project())
            return
        except Exception as e:
            if i == retries - 1:
                print(f"[startup] could not load project into Neo4j: {e}")
            time.sleep(2)


def _warm_llm() -> None:
    """Fire one tiny call so the first REAL question doesn't also pay for
    client construction + TLS handshake + cold-path latency. Best-effort: a
    missing key or offline network must never stop the API from booting (the
    CPM engine, risk radar and Monte-Carlo don't need an LLM at all)."""
    try:
        from agents.llm import has_key, invoke_text
        if has_key():
            invoke_text("Reply with exactly: READY", 0)
            print("[startup] LLM warm")
    except Exception as e:
        print(f"[startup] LLM warmup skipped: {str(e)[:120]}")


@app.on_event("startup")
def _startup():
    _load_active_into_neo4j()
    threading.Thread(target=_warm_llm, daemon=True).start()


def _jsonable(obj):
    """Recursively convert dates/datetimes to ISO strings for JSON."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


# ------------------------------------------------------------------ models
class CascadeReq(BaseModel):
    material_id: str
    delay_days: int = 5


class CascadeMultiReq(BaseModel):
    delays: dict[str, int]   # {material_id: delay_days}


class AskReq(BaseModel):
    question: str
    scene: dict | None = None   # live on-screen Cascade Simulator state, if any


# ------------------------------------------------------------------ routes
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/project")
def project():
    """Graph summary + nodes/edges for the visualization."""
    g = get_graph()
    kinds = [d.get("kind") for _, d in g.nodes(data=True)]
    nodes = [
        {"id": n, "kind": d.get("kind"), "name": d.get("name", n),
         "confidence": d.get("confidence"),
         "shipment_status": d.get("shipment_status"),
         "supplier": d.get("supplier"),
         "needs_materials": d.get("needs_materials"),
         "depends_on": d.get("depends_on")}
        for n, d in g.nodes(data=True)
    ]
    edges = [{"source": u, "target": v, "kind": d.get("kind")}
             for u, v, d in g.edges(data=True)]
    # Is the user looking at the bundled demo, or a project they built? The UI
    # uses this to label demo data as synthetic on screen — an honesty claim
    # only counts if it's visible in the app, not just in the README.
    try:
        demo = any(p.get("active") and p.get("seed") for p in projects.list_projects())
    except Exception:
        demo = False

    return {
        "name": g.graph.get("name"),
        "handover": g.graph.get("handover"),
        "demo": demo,
        "counts": {
            "suppliers": kinds.count(SUPPLIER),
            "materials": kinds.count(MATERIAL),
            "activities": kinds.count(ACTIVITY),
            "edges": g.number_of_edges(),
        },
        "nodes": nodes, "edges": edges,
    }


@app.get("/api/materials")
def materials():
    g = get_graph()
    return [{"id": n, "name": d["name"], "supplier": d.get("supplier"),
             "confidence": d.get("confidence")}
            for n, d in g.nodes(data=True) if d.get("kind") == MATERIAL]


@app.post("/api/cascade")
def cascade(req: CascadeReq):
    g = get_graph()
    if g.nodes.get(req.material_id, {}).get("kind") != MATERIAL:
        raise HTTPException(400, f"'{req.material_id}' is not a material")
    return _jsonable(asdict(run_cascade(g, req.material_id, req.delay_days)))


@app.post("/api/cascade-multi")
def cascade_multi(req: CascadeMultiReq):
    """Combined cascade over several materials delayed at once."""
    g = get_graph()
    return _jsonable(asdict(run_cascade_multi(g, req.delays)))


@app.get("/api/risk")
def risk():
    return [_jsonable(asdict(r)) for r in risk_radar(get_graph())]


@app.get("/api/montecarlo")
def montecarlo():
    return _jsonable(asdict(simulate()))


@app.get("/api/alt-supplier/{material_id}")
def alt_supplier(material_id: str):
    return _jsonable(recommend(material_id))


@app.get("/api/today")
def today():
    """The morning brief: what needs attention, in plain language, ranked."""
    from today import brief                                  # noqa: PLC0415
    return _jsonable(brief(projects.get_active_project()))


# ---------------------------------------------------------------- money
@app.get("/api/money")
def money_settings():
    """The rupee assumptions behind every cost shown in the UI, each labelled
    'your number' or 'assumed' with the reasoning behind the default."""
    return money.commercials(projects.get_active_project())


@app.put("/api/money")
def money_update(patch: dict):
    """Edit the money assumptions. Send a key as null to reset it."""
    try:
        clean = money.clean_patch(patch)
    except ValueError as e:
        raise HTTPException(400, str(e))
    projects.set_commercials(clean)
    return money.commercials(projects.get_active_project())


@app.post("/api/cost-of-delay")
def cost_of_delay(req: dict):
    """What a handover slip of N days costs, itemised."""
    return money.cost_of_delay(int(req.get("slip_days", 0)),
                               projects.get_active_project())


@app.post("/api/recovery")
def recovery(req: CascadeMultiReq):
    """Ranked, priced ways to protect the handover date for these delays."""
    return _jsonable(recovery_options(req.delays, projects.get_active_project()))


@app.post("/api/messages")
def messages(req: CascadeMultiReq):
    """Ready-to-send supplier + client messages for the current situation."""
    from comms import drafts                                # noqa: PLC0415
    return _jsonable(drafts(req.delays, projects.get_active_project()))


@app.post("/api/cost-of-waiting")
def cost_of_waiting(req: dict):
    """Week by week: what protecting the handover costs, and when the cheap
    options physically stop being available."""
    from timemachine import cost_of_waiting as cow          # noqa: PLC0415
    try:
        return _jsonable(cow(req.get("material_id", ""), int(req.get("delay_days", 7)),
                             project=projects.get_active_project()))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/ask")
def ask(req: AskReq):
    """Ask Foreman is the one surface that needs the LLM. A public deployment
    can lose it (key unset, free-tier quota spent) — when that happens say so
    in one sentence instead of returning a stack trace. Every other surface,
    including the whole cascade/money/recovery number path, is LLM-free and
    keeps working."""
    from agents.llm import has_key                           # noqa: PLC0415
    if not has_key():
        raise HTTPException(503, "Ask Foreman needs a Gemini key on the server. "
                                 "The cascade, risk radar, money and recovery "
                                 "views don't use an LLM and are unaffected.")
    try:
        return _jsonable(brain_answer(req.question, req.scene))
    except Exception as e:
        first = str(e).split("\n")[0][:160]
        raise HTTPException(503, f"The reasoning agent could not finish that "
                                 f"question ({first}). The graph, cascade and "
                                 f"money views are unaffected.")


@app.post("/api/build-graph")
def build_graph():
    return _jsonable(build_graph_from_docs(write=True))


@app.get("/api/docs")
def docs_list():
    """Every doc the next Build-from-Docs run will ingest (seed + uploaded)."""
    return list_docs()


@app.post("/api/docs/upload")
async def docs_upload(files: list[UploadFile] = File(...)):
    """Add live-uploaded documents to the corpus. Plain text (.txt) only —
    they get read as raw text and passed straight to the extraction LLM."""
    saved = []
    for f in files:
        if not (f.filename or "").lower().endswith(".txt"):
            raise HTTPException(400, f"{f.filename}: only .txt documents are supported")
        content = await f.read()
        if len(content) > 200_000:
            raise HTTPException(400, f"{f.filename}: too large (max 200KB)")
        saved.append(save_uploaded_doc(f.filename, content))
    return {"saved": saved, "docs": list_docs()}


@app.post("/api/docs/reset")
def docs_reset():
    """Drop all uploaded docs, restoring the fixed demo corpus."""
    removed = reset_docs()
    return {"removed": removed, "docs": list_docs()}


# ------------------------------------------------------------ projects
@app.get("/api/projects")
def projects_list():
    return projects.list_projects()


@app.post("/api/projects")
def projects_create(data: dict):
    """Create a project from user-entered data, make it active, load it."""
    try:
        pid = projects.create_project(data)
    except (KeyError, ValueError) as e:
        raise HTTPException(400, f"Invalid project: {e}")
    load_to_neo4j_if_enabled(projects.get_active_project())
    return {"id": pid, "active": pid}


@app.post("/api/projects/draft")
def projects_draft(req: dict):
    """Describe a project in plain English -> a validated DRAFT to confirm.

    Nothing is saved. The user reviews what we understood, then posts it to
    /api/projects like any other project.
    """
    from agents.project_builder import draft                 # noqa: PLC0415
    try:
        return draft(req.get("text", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.post("/api/projects/draft-file")
async def projects_draft_file(file: UploadFile = File(...)):
    """Same, from the spreadsheet the user already keeps."""
    from agents.project_builder import draft, spreadsheet_to_text   # noqa: PLC0415
    content = await file.read()
    if len(content) > 2_000_000:
        raise HTTPException(400, f"{file.filename}: too large (max 2MB)")
    try:
        text = spreadsheet_to_text(file.filename or "", content)
        if not text.strip():
            raise ValueError("that file looks empty")
        return {**draft(text), "extracted": text[:4000]}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.post("/api/projects/{pid}/activate")
def projects_activate(pid: str):
    try:
        projects.set_active(pid)
    except ValueError as e:
        raise HTTPException(404, str(e))
    load_to_neo4j_if_enabled(projects.get_active_project())
    return {"active": pid}


@app.delete("/api/projects/{pid}")
def projects_delete(pid: str):
    try:
        projects.delete_project(pid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    load_to_neo4j_if_enabled(projects.get_active_project())
    return {"active": projects.get_active_id()}


# ------------------------------------------------------- static SPA (prod)
# In production Foreman is ONE service: this API also serves the built React
# app. Same origin means no CORS, no API base URL to configure, and one URL to
# hand a judge. Mounted last so every /api route above wins the match first.
_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"

if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """Serve real files; hand everything else to the client-side router."""
        if full_path.startswith("api/"):
            raise HTTPException(404, "no such endpoint")
        candidate = (_DIST / full_path).resolve()
        # resolve() + is_relative_to keeps ../ out of the served tree
        if full_path and candidate.is_file() and candidate.is_relative_to(_DIST):
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
else:
    print("[startup] web/dist not built — API-only mode (dev uses the Vite proxy)")
