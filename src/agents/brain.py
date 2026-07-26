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

# Signals that the user is describing a delay scenario to simulate.
_WHATIF = re.compile(
    r"\b(what if|what happens if|if .+ (slips?|delayed?|late|slip)|"
    r"slips? \d+|delayed? by|push(ed)? back|misses? its? roj)\b", re.I)


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
        return res
    if _WHATIF.search(question):
        res = explain_cascade(question)
        res["mode"] = "cascade"
        return res
    res = ask(question)
    return {
        "answer": res.get("answer", ""),
        "citations": res.get("citations", []),
        "trace": res.get("trace", []),
        "mode": "query",
    }


if __name__ == "__main__":
    for q in ["Which suppliers are least reliable?",
              "What if the switchgear slips 12 days?"]:
        r = answer(q)
        print(f"\n[{r['mode']}] Q: {q}\nA: {r['answer'][:200]}")
