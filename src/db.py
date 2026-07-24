"""Foreman — Neo4j store + NetworkX mirror.

Neo4j is the source of truth for the construction knowledge graph (and the
surface the NL->Cypher agent queries). The CPM cascade math, however, runs on
an in-memory NetworkX mirror built from Neo4j, so the proven Stage-1 engine
(`cascade.py`, `risk.py`) keeps working unchanged.

    project.json  --load-->  Neo4j  --graph_from_neo4j-->  NetworkX  --> CPM

Usage:
    python -m src.db --load     # (re)load project.json into Neo4j
    python -m src.db --verify   # print counts + a sample Cypher result
"""

from __future__ import annotations

import os
from pathlib import Path

import networkx as nx
from dotenv import load_dotenv

try:
    from src.graph import (ACTIVITY, DEPENDS_ON, FEEDS, MATERIAL, SUPPLIER,
                           SUPPLIES, build_graph, load_project)
except ImportError:  # when src/ is already on sys.path (Streamlit)
    from graph import (ACTIVITY, DEPENDS_ON, FEEDS, MATERIAL, SUPPLIER,
                       SUPPLIES, build_graph, load_project)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "foreman123")

# Node labels in Neo4j (title-case of the NetworkX `kind` strings).
_LABEL = {SUPPLIER: "Supplier", MATERIAL: "Material", ACTIVITY: "Activity"}


def _driver():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# --------------------------------------------------------------------- load
def load_to_neo4j(project: dict | None = None) -> dict:
    """Wipe and repopulate Neo4j from the project dict. Returns counts."""
    project = project or load_project()
    with _driver() as drv, drv.session() as s:
        s.run("MATCH (n) DETACH DELETE n")

        # Project meta node (carries handover milestone for the graph mirror).
        s.run(
            "CREATE (:Project {name:$name, handover:$handover, description:$desc})",
            name=project["project"]["name"],
            handover=project["project"]["handover_milestone"],
            desc=project["project"].get("description", ""),
        )

        for sup in project["suppliers"]:
            s.run("CREATE (n:Supplier $p) SET n.kind=$k", p=sup, k=SUPPLIER)

        for mat in project["materials"]:
            s.run("CREATE (n:Material $p) SET n.kind=$k", p=mat, k=MATERIAL)
            s.run(
                "MATCH (a:Supplier {id:$s}),(b:Material {id:$m}) "
                "CREATE (a)-[:SUPPLIES {kind:$k, confidence:$c}]->(b)",
                s=mat["supplier"], m=mat["id"], k=SUPPLIES, c=mat["confidence"],
            )

        for act in project["activities"]:
            s.run("CREATE (n:Activity $p) SET n.kind=$k", p=act, k=ACTIVITY)

        # Edges that carry the flow of consequence.
        for act in project["activities"]:
            for mat_id in act["needs_materials"]:
                mat = next(m for m in project["materials"] if m["id"] == mat_id)
                s.run(
                    "MATCH (a:Material {id:$m}),(b:Activity {id:$act}) "
                    "CREATE (a)-[:FEEDS_ACTIVITY {kind:$k, roj_date:$roj, confidence:$c}]->(b)",
                    m=mat_id, act=act["id"], k=FEEDS,
                    roj=mat["roj_date"], c=mat["confidence"],
                )
            for upstream in act["depends_on"]:
                s.run(
                    "MATCH (a:Activity {id:$u}),(b:Activity {id:$act}) "
                    "CREATE (a)-[:DEPENDS_ON {kind:$k, confidence:1.0}]->(b)",
                    u=upstream, act=act["id"], k=DEPENDS_ON,
                )

    return verify(silent=True)


# ---------------------------------------------------------- NetworkX mirror
def graph_from_neo4j() -> nx.DiGraph:
    """Rebuild the exact Stage-1 DiGraph shape from Neo4j.

    Node ids + attributes and edge kinds match `graph.build_graph` so the CPM
    engine consumes it identically.
    """
    with _driver() as drv, drv.session() as s:
        meta = s.run(
            "MATCH (p:Project) RETURN p.name AS name, p.handover AS handover"
        ).single()
        g = nx.DiGraph(name=meta["name"], handover=meta["handover"])

        for rec in s.run("MATCH (n) WHERE n.id IS NOT NULL RETURN n"):
            props = dict(rec["n"])
            g.add_node(props["id"], **props)

        for rec in s.run(
            "MATCH (a)-[r]->(b) WHERE a.id IS NOT NULL AND b.id IS NOT NULL "
            "RETURN a.id AS src, b.id AS dst, type(r) AS t, properties(r) AS p"
        ):
            g.add_edge(rec["src"], rec["dst"], **rec["p"])
    return g


def get_graph() -> nx.DiGraph:
    """The graph the app/agents use: Neo4j-backed, JSON fallback for resilience."""
    try:
        return graph_from_neo4j()
    except Exception as e:  # Docker down mid-demo -> never crash the UI
        print(f"[db] Neo4j unavailable ({e}); falling back to project.json")
        return build_graph()


# --------------------------------------------------------------------- misc
SCHEMA_HINT = """\
Node labels & key properties:
  (:Supplier   {id, name, location, reliability})
  (:Material   {id, name, supplier, po, submittal_status, fabrication_status,
                shipment_status, current_location, lead_time_days, roj_date,
                expected_arrival, confidence, confidence_source})
  (:Activity   {id, name, duration_days, depends_on, needs_materials, early_start})
  (:Project    {name, handover})
Relationships. ALL arrows point in the direction a DELAY travels downstream:
  (:Supplier)-[:SUPPLIES {confidence}]->(:Material)
  (:Material)-[:FEEDS_ACTIVITY {roj_date, confidence}]->(:Activity)
  (:Activity prerequisite)-[:DEPENDS_ON {confidence}]->(:Activity dependent)

IMPORTANT direction rules (the arrow is prerequisite -> dependent):
  * "what activities DEPEND ON X" (downstream of X, X is the prerequisite):
      MATCH (x:Activity)-[:DEPENDS_ON*]->(d:Activity)
      WHERE toLower(x.name) CONTAINS toLower('<X>') RETURN DISTINCT d
  * "what does X depend on" (its prerequisites, upstream):
      MATCH (p:Activity)-[:DEPENDS_ON*]->(x:Activity)
      WHERE toLower(x.name) CONTAINS toLower('<X>') RETURN DISTINCT p
  * blast radius of a material delay = everything reachable following arrows:
      MATCH (m:Material)-[*]->(a:Activity) WHERE m.id='MAT-x' RETURN DISTINCT a
The handover milestone is the Activity whose id == (:Project).handover.
"""


def run_cypher(query: str, params: dict | None = None) -> list[dict]:
    """Execute read Cypher, return rows as dicts (used by the query agent)."""
    with _driver() as drv, drv.session() as s:
        return [r.data() for r in s.run(query, params or {})]


def update_material(mat_id: str, props: dict) -> None:
    """Write extracted evidence (confidence, source, conflict flag) onto a
    Material node. Used by the KG Builder to keep status current from docs."""
    with _driver() as drv, drv.session() as s:
        s.run("MATCH (m:Material {id:$id}) SET m += $props", id=mat_id, props=props)


def verify(silent: bool = False) -> dict:
    with _driver() as drv, drv.session() as s:
        counts = {
            "suppliers": s.run("MATCH (n:Supplier) RETURN count(n) AS c").single()["c"],
            "materials": s.run("MATCH (n:Material) RETURN count(n) AS c").single()["c"],
            "activities": s.run("MATCH (n:Activity) RETURN count(n) AS c").single()["c"],
            "relationships": s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"],
        }
    if not silent:
        print("Neo4j contents:", counts)
        sample = run_cypher(
            "MATCH (s:Supplier)-[:SUPPLIES]->(m:Material) "
            "WHERE m.confidence < 0.75 "
            "RETURN m.id AS material, m.name AS name, s.name AS supplier, "
            "m.confidence AS confidence ORDER BY m.confidence"
        )
        print("\nSample Cypher (low-confidence materials):")
        for row in sample:
            print(f"  {row['material']} {row['name']} <- {row['supplier']} "
                  f"(conf {row['confidence']})")
    return counts


if __name__ == "__main__":
    import sys
    if "--load" in sys.argv:
        print("Loading project.json into Neo4j...")
        print("Loaded:", load_to_neo4j())
    if "--verify" in sys.argv or "--load" in sys.argv:
        verify()
