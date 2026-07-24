"""Agent B — Query / Reasoning agent (the "ask the brain" surface).

A LangGraph pipeline that answers natural-language questions about the project
by reasoning over the Neo4j knowledge graph:

    plan (classify + write Cypher) -> execute (self-correct on error) -> answer

Every step is recorded in a `trace` so the UI can SHOW the brain reasoning
(classification, the Cypher it wrote, the rows it got, the grounded answer)
rather than presenting a black-box reply. Answers cite the graph nodes used.

Blueprint: arXiv 2507.17273 (KG+LLM warehouse bottleneck reasoning) — query
classifier + NL->Cypher with an execute/error-correct loop.

Design notes:
- classify + Cypher are produced in ONE LLM call (JSON) to stay well under the
  free-tier request budget — 2 calls/question in the happy path.
- Read-only guard: generated Cypher is rejected if it contains a write clause.
- Fuzzy name matching is enforced in the prompt (users say "switchgear", the
  graph stores "4000A LV switchgear lineup").
- The iterative sub-question loop + self-reflection (deep diagnostic questions)
  is layered on in Day 3.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

try:
    from src.db import SCHEMA_HINT, run_cypher
    from src.agents.llm import invoke_text
except ImportError:
    from db import SCHEMA_HINT, run_cypher
    from agents.llm import invoke_text

MAX_CYPHER_RETRIES = 2
_WRITE = re.compile(r"\b(CREATE|DELETE|DETACH|SET|MERGE|REMOVE|DROP|LOAD\s+CSV)\b", re.I)


class QueryState(TypedDict, total=False):
    question: str
    category: str            # "factual" | "diagnostic"
    cypher: str
    rows: list[dict]
    error: str | None
    retries: int
    answer: str
    citations: list[str]
    trace: list[dict]


def _add_trace(state: QueryState, step: str, detail: Any) -> None:
    state.setdefault("trace", []).append({"step": step, "detail": detail})


def _strip_fences(text: str) -> str:
    text = text.strip()
    m = re.search(r"```(?:cypher|json)?\s*(.*?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip()


def _parse_plan(raw: str) -> tuple[str, str]:
    """Pull {category, cypher} out of the LLM's JSON reply, tolerant of noise."""
    body = _strip_fences(raw)
    try:
        obj = json.loads(body)
        cat = str(obj.get("category", "factual")).lower()
        cyp = str(obj.get("cypher", "")).strip().rstrip(";").strip()
        return ("diagnostic" if "diag" in cat else "factual"), cyp
    except Exception:
        # Fallback: treat the whole thing as Cypher.
        cyp = body.strip().rstrip(";").strip()
        return "factual", cyp


# ------------------------------------------------------------------ nodes
def plan_node(state: QueryState) -> QueryState:
    q = state["question"]
    err = state.get("error")
    fix = ""
    if err:
        fix = (
            f"\nYour previous Cypher FAILED or returned nothing:\n"
            f"  query: {state.get('cypher','')}\n  problem: {err}\n"
            "Write a corrected read-only query (check names use CONTAINS, not =)."
        )
    prompt = (
        "You are Foreman's query planner over a Neo4j construction supply-chain "
        "graph. Given a question, (1) classify it and (2) write ONE read-only "
        "Cypher query that answers it.\n\n"
        f"{SCHEMA_HINT}\n"
        "RULES:\n"
        "- category: 'factual' (lookup/list/count/status/date) or 'diagnostic' "
        "(why / what-if / impact / risk reasoning).\n"
        "- Cypher must be READ-ONLY (no CREATE/MERGE/SET/DELETE).\n"
        "- For any material/supplier/activity NAME, match fuzzily: "
        "toLower(n.name) CONTAINS toLower('<keyword>'). NEVER use n.name = '...'.\n"
        "- Always RETURN node ids AND names (and relevant dates/confidence) so "
        "the answer can cite them.\n"
        "- Respond ONLY as JSON: {\"category\": \"...\", \"cypher\": \"...\"}\n\n"
        f"Question: {q}{fix}"
    )
    cat, cyp = _parse_plan(invoke_text(prompt, 0))
    state["category"] = cat
    state["cypher"] = cyp
    _add_trace(state, "classify", f"'{q}' -> {cat}")
    _add_trace(state, "cypher", cyp)
    return state


def execute_node(state: QueryState) -> QueryState:
    cypher = state.get("cypher", "")
    if not cypher:
        state["error"] = "empty query"
        state["rows"] = []
        _add_trace(state, "execute", "no query produced")
        state["retries"] = state.get("retries", 0) + 1
        return state
    if _WRITE.search(cypher):
        state["error"] = "Rejected: query contains a write clause (read-only only)."
        state["rows"] = []
        _add_trace(state, "execute", "BLOCKED write query")
        return state
    try:
        rows = run_cypher(cypher)
        state["rows"] = rows
        # Empty result on first try -> treat as a miss worth one correction.
        if not rows and state.get("retries", 0) < MAX_CYPHER_RETRIES:
            state["error"] = "query returned 0 rows — likely a name/filter mismatch"
            state["retries"] = state.get("retries", 0) + 1
            _add_trace(state, "execute", "0 rows -> will retry")
        else:
            state["error"] = None
            _add_trace(state, "execute", f"{len(rows)} row(s)")
    except Exception as e:
        state["error"] = str(e).split("\n")[0][:300]
        state["retries"] = state.get("retries", 0) + 1
        _add_trace(state, "execute", f"error (retry {state['retries']}): {state['error']}")
    return state


def _route_after_execute(state: QueryState) -> str:
    if state.get("error") and state.get("retries", 0) <= MAX_CYPHER_RETRIES \
            and "Rejected" not in (state.get("error") or ""):
        return "retry"
    return "answer"


def answer_node(state: QueryState) -> QueryState:
    q = state["question"]
    rows = state.get("rows", [])
    if not rows:
        state["answer"] = (
            "I couldn't find that in the project graph. Try naming a specific "
            "material, supplier, or activity — e.g. 'the switchgear' or 'MAT-2'."
        )
        state["citations"] = []
        _add_trace(state, "answer", "no rows / gave guidance")
        return state

    cites: list[str] = []
    for r in rows:
        for v in r.values():
            if isinstance(v, str) and re.fullmatch(r"(MAT|SUP|ACT|PO)-\d+", v):
                cites.append(v)
    cites = sorted(set(cites))

    prompt = (
        "You are Foreman, a construction supply-chain analyst. Answer the "
        "question from ONLY this graph data — concise, concrete, no fluff. "
        "Name specific ids/names/dates. If confidence values are present, note "
        "them (they reflect how sure we are of a material's status).\n"
        f"Question: {q}\nGraph data: {rows}"
    )
    state["answer"] = invoke_text(prompt, 0.3).strip()
    state["citations"] = cites
    _add_trace(state, "answer", f"cited {cites}")
    return state


# ------------------------------------------------------------------ build
def build_query_agent():
    g = StateGraph(QueryState)
    g.add_node("plan", plan_node)
    g.add_node("execute", execute_node)
    g.add_node("answer", answer_node)
    g.add_edge(START, "plan")
    g.add_edge("plan", "execute")
    g.add_conditional_edges("execute", _route_after_execute,
                            {"retry": "plan", "answer": "answer"})
    g.add_edge("answer", END)
    return g.compile()


_AGENT = None


def ask(question: str) -> QueryState:
    """Answer a question; returns full state (answer + citations + trace)."""
    global _AGENT
    if _AGENT is None:
        _AGENT = build_query_agent()
    return _AGENT.invoke({"question": question, "retries": 0, "trace": []})


if __name__ == "__main__":
    for q in [
        "Which materials have confidence below 0.75?",
        "What is the switchgear's expected arrival and who supplies it?",
        "How many activities depend on the switchgear installation?",
    ]:
        print("\n" + "=" * 70 + f"\nQ: {q}")
        res = ask(q)
        print(f"[{res['category']}] cypher: {res['cypher']}")
        print("A:", res["answer"])
        print("cites:", res.get("citations"))
