"""Foreman knowledge graph.

Builds a directed knowledge graph of the post-order construction supply chain:

    Supplier -> Material -> ScheduleActivity -> ... -> Handover milestone

Every node and edge carries metadata (status, dates, confidence) so agents can
reason over it. Prototype uses NetworkX; the same schema maps 1:1 onto Neo4j
for the production version.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "project.json"

# Node kinds
SUPPLIER = "supplier"
MATERIAL = "material"
ACTIVITY = "activity"

# Edge kinds
SUPPLIES = "SUPPLIES"            # supplier -> material
FEEDS = "FEEDS_ACTIVITY"         # material -> activity that installs it
DEPENDS_ON = "DEPENDS_ON"        # activity -> downstream activity


def load_project(path: Path = DATA_PATH) -> dict:
    """Load the raw project JSON."""
    with open(path) as f:
        return json.load(f)


def build_graph(project: dict | None = None) -> nx.DiGraph:
    """Build the knowledge graph from project data.

    Edge direction follows the flow of consequence: a delay travels
    supplier -> material -> activity -> dependent activities -> handover.
    """
    if project is None:
        project = load_project()

    g = nx.DiGraph(name=project["project"]["name"],
                   handover=project["project"]["handover_milestone"])

    for sup in project["suppliers"]:
        g.add_node(sup["id"], kind=SUPPLIER, **sup)

    for mat in project["materials"]:
        g.add_node(mat["id"], kind=MATERIAL, **mat)
        g.add_edge(mat["supplier"], mat["id"], kind=SUPPLIES,
                   confidence=mat["confidence"])

    for act in project["activities"]:
        g.add_node(act["id"], kind=ACTIVITY, **act)

    # Wire materials -> activities, activities -> activities
    for act in project["activities"]:
        for mat_id in act["needs_materials"]:
            mat = g.nodes[mat_id]
            g.add_edge(mat_id, act["id"], kind=FEEDS,
                       roj_date=mat["roj_date"],
                       confidence=mat["confidence"])
        for upstream in act["depends_on"]:
            g.add_edge(upstream, act["id"], kind=DEPENDS_ON, confidence=1.0)

    return g


def downstream_activities(g: nx.DiGraph, node_id: str) -> list[str]:
    """All activities reachable from a node (the potential blast radius)."""
    return [n for n in nx.descendants(g, node_id)
            if g.nodes[n]["kind"] == ACTIVITY]


def graph_summary(g: nx.DiGraph) -> dict:
    """Quick stats used by the UI header."""
    kinds = [d["kind"] for _, d in g.nodes(data=True)]
    return {
        "project": g.graph["name"],
        "suppliers": kinds.count(SUPPLIER),
        "materials": kinds.count(MATERIAL),
        "activities": kinds.count(ACTIVITY),
        "edges": g.number_of_edges(),
    }


if __name__ == "__main__":
    g = build_graph()
    print(json.dumps(graph_summary(g), indent=2))
    print("\nBlast radius of MAT-2 (switchgear):",
          downstream_activities(g, "MAT-2"))
