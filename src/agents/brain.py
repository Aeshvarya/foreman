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

from agents.cascade_agent import explain_cascade   # noqa: E402
from agents.query_agent import ask                  # noqa: E402

# Signals that the user is describing a delay scenario to simulate.
_WHATIF = re.compile(
    r"\b(what if|what happens if|if .+ (slips?|delayed?|late|slip)|"
    r"slips? \d+|delayed? by|push(ed)? back|misses? its? roj)\b", re.I)


def answer(question: str) -> dict:
    """Route and answer. Returns {answer, citations, trace, mode}."""
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
