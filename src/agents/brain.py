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

# "Which items are riskiest / have the least room / should I chase?" is exactly
# what the risk radar computes. Answering it from the radar keeps the answer to
# the same verified numbers the Radar page shows, and needs neither the graph
# database nor a language model. "Why ..." questions still go to the query
# agent, which reasons about causes.
_RANKING = re.compile(
    r"\b(most|biggest|highest|top|worst|riskiest|which|what)\b.*"
    r"\b(risk|risky|at risk|critical|least room|tightest|worr(?:y|ied)|attention|chase|urgent)\b"
    r"|\bbreaking points?\b|\bleast (?:room|float|slack)\b", re.I)
_WHY = re.compile(r"\bwhy\b", re.I)


def _radar_answer(top: int = 5) -> dict:
    from risk import MAX_PROBE_DAYS, risk_radar       # noqa: PLC0415
    from today import _how_sure                        # noqa: PLC0415
    radar = risk_radar(get_graph())
    tight = sorted((r for r in radar if r.breaking_point_days is not None),
                   key=lambda r: (r.breaking_point_days, -r.risk_score))[:top]
    trace = [{"step": "radar",
              "detail": f"breaking point for {len(radar)} items from the schedule's longest paths",
              "say": f"Worked out how many days each of the {len(radar)} tracked items can slip "
                     "before the handover date moves."},
             {"step": "rank", "detail": ", ".join(f"{r.material_id}={r.breaking_point_days}d" for r in tight),
              "say": "Ranked them, least room first."}]
    if not tight:
        return {"answer": f"Nothing can move the handover date on its own: every tracked item can slip "
                          f"more than {MAX_PROBE_DAYS} days before it does.",
                "citations": [], "trace": trace}
    lines = [f"{i}. **{r.name}** — {r.breaking_point_days} day{'s' if r.breaking_point_days != 1 else ''} "
             f"of room (status: {_how_sure(r.confidence, r.confidence_source)})"
             for i, r in enumerate(tight, 1)]
    more = len([r for r in radar if r.breaking_point_days is not None]) - len(tight)
    answer = ("The items with the least room before the handover date moves:\n\n" + "\n".join(lines)
              + (f"\n\n{more} more can move it too, with more room." if more > 0 else ""))
    return {"answer": answer, "citations": [r.material_id for r in tight], "trace": trace}


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
    if _RANKING.search(question) and not _WHY.search(question):
        res = _radar_answer()
        res["mode"] = "radar"
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
