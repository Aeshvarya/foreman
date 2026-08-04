"""Foreman brain — routes a question to the right agent.

- A delay "what-if" (does the handover break if X slips N days?) -> Cascade
  agent (grounded CPM math).
- Anything else (status, lists, counts, who/where/when) -> Query agent
  (NL->Cypher over Neo4j).

Both return the same shape {answer, citations, trace, mode} so the UI renders
them identically.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.cascade_agent import explain_cascade, narrate_scene   # noqa: E402
from agents.query_agent import ask                  # noqa: E402
from db import get_graph                            # noqa: E402

# Signals that the user is describing a delay scenario to simulate.
_WHATIF = re.compile(
    r"\b(what if|what happens if|if .+ (slips?|delayed?|late|slip)|"
    r"slips? \d+|delayed? by|push(ed)? back|misses? its? roj)\b", re.I)


def _label(citations: list) -> list[dict]:
    """Turn cited graph ids into things a human recognises.

    The agents cite nodes by id (MAT-6, SUP-2) because that is what the graph
    returns and what the technical trace should show. Nobody on a building site
    calls a generator "MAT-6", so every citation that reaches the screen is
    resolved to its real name here — one place, so the query agent, the cascade
    agent and the scene narrator all benefit. The id travels alongside for the
    technical view and as a fallback if a node has since gone.
    """
    try:
        g = get_graph()
    except Exception:
        return [{"id": c, "name": c} for c in citations]
    out = []
    for c in citations:
        node = g.nodes.get(c) if hasattr(g, "nodes") else None
        out.append({"id": c, "name": (node or {}).get("name", c) if node else c})
    return out


def answer(question: str, scene: dict | None = None) -> dict:
    """Route and answer. Returns {answer, citations, trace, mode}.

    If `scene` is given (the frontend's live on-screen Cascade Simulator
    state), it always wins — bypassing the what-if regex entirely, since a
    scene full of "delayed"/"slip" words would otherwise get misrouted into
    re-parsing a brand new delay scenario instead of explaining the one
    already computed and sitting on screen.
    """
    if scene is not None:
        res = narrate_scene(question, scene)
        res["mode"] = "scene"
        res["citations"] = _label(res.get("citations", []))
        return res
    if _WHATIF.search(question):
        res = explain_cascade(question)
        res["mode"] = "cascade"
        res["citations"] = _label(res.get("citations", []))
        return res
    res = ask(question)
    return {
        "answer": res.get("answer", ""),
        "citations": _label(res.get("citations", [])),
        "trace": res.get("trace", []),
        "mode": "query",
    }


if __name__ == "__main__":
    for q in ["Which suppliers are least reliable?",
              "What if the switchgear slips 12 days?"]:
        r = answer(q)
        print(f"\n[{r['mode']}] Q: {q}\nA: {r['answer'][:200]}")
