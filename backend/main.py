"""Foreman API — FastAPI layer over the reasoning brain.

Thin wrappers around the already-built + tested brain modules (nothing in
`src/` changes). The premium web frontend (../web) calls these endpoints.

Run:  uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Make src/ importable so the brain modules' bare imports resolve.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db import get_graph                       # noqa: E402
from cascade import run_cascade                # noqa: E402
from risk import risk_radar                    # noqa: E402
from montecarlo import simulate                # noqa: E402
from alt_supplier import recommend             # noqa: E402
from agents.brain import answer as brain_answer          # noqa: E402
from agents.kg_builder import build_graph_from_docs      # noqa: E402
from graph import MATERIAL, SUPPLIER, ACTIVITY           # noqa: E402

app = FastAPI(title="Foreman API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


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


class AskReq(BaseModel):
    question: str


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
    return {
        "name": g.graph.get("name"),
        "handover": g.graph.get("handover"),
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
    return _jsonable(asdict(run_cascade(g, req.material_id, req.delay_days)))


@app.get("/api/risk")
def risk():
    return [_jsonable(asdict(r)) for r in risk_radar(get_graph())]


@app.get("/api/montecarlo")
def montecarlo():
    return _jsonable(asdict(simulate()))


@app.get("/api/alt-supplier/{material_id}")
def alt_supplier(material_id: str):
    return _jsonable(recommend(material_id))


@app.post("/api/ask")
def ask(req: AskReq):
    return _jsonable(brain_answer(req.question))


@app.post("/api/build-graph")
def build_graph():
    return _jsonable(build_graph_from_docs(write=True))
