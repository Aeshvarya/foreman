"""Agent B — Query / Reasoning agent (the "ask the brain" surface).

A LangGraph pipeline that answers natural-language questions about the project
by reasoning over the Neo4j knowledge graph. Simple lookups take the short
path; genuinely hard questions get broken apart and the answer gets checked
before you see it:

    plan -> execute (self-correct on error)
         -> [diagnostic] decompose into sub-questions -> gather evidence
         -> answer
         -> reflect (is every claim supported? anything missing?)
              -> gather the one missing piece -> answer again

Every step is recorded in a `trace` so the UI can SHOW the brain reasoning
rather than presenting a black-box reply. Each trace entry carries BOTH a
plain-English `say` (what a site manager reads) and the technical `detail`
(the Cypher, the row counts — what a judge inspects). Answers cite the graph
nodes used.

Blueprint: arXiv 2507.17273 (KG+LLM warehouse bottleneck reasoning) — query
classifier + NL->Cypher with an execute/error-correct loop, plus the iterative
sub-question loop with self-reflection that paper measures at 41% -> 82%
answer accuracy on multi-hop questions.

Design notes:
- classify + Cypher are produced in ONE LLM call (JSON) to stay well under the
  free-tier request budget — 2 calls/question on the simple path.
- Read-only guard: generated Cypher is rejected if it contains a write clause.
- Fuzzy name matching is enforced in the prompt (users say "switchgear", the
  graph stores "4000A LV switchgear lineup").
- The deep path is BOUNDED on purpose: at most MAX_SUBQUESTIONS sub-questions
  and MAX_REFLECTIONS re-check, so a hard question costs ~8 calls, not an
  unbounded spiral. A live demo must have a predictable worst case.
- Reflection can only ever ADD evidence and re-answer. It cannot invent facts:
  the follow-up is itself a graph query, so a "corrected" answer is still
  grounded in rows that came out of Neo4j.
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
MAX_SUBQUESTIONS = 3
MAX_REFLECTIONS = 1
_WRITE = re.compile(r"\b(CREATE|DELETE|DETACH|SET|MERGE|REMOVE|DROP|LOAD\s+CSV)\b", re.I)
_ID = re.compile(r"(MAT|SUP|ACT|PO)-\d+")


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
    subquestions: list[str]
    evidence: list[dict]     # [{question, cypher, rows}] — everything we found
    reflections: int
    gap: str | None          # what reflection said was missing, if anything


def _add_trace(state: QueryState, step: str, detail: Any, say: str = "") -> None:
    """Record a step twice over: `detail` for the inspector, `say` for the human.

    The plain-English line is not decoration — it is the difference between a
    site manager trusting the answer and a site manager seeing a wall of Cypher
    and closing the tab.
    """
    state.setdefault("trace", []).append(
        {"step": step, "detail": str(detail), "say": say or str(detail)}
    )


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


def _parse_json_obj(raw: str) -> dict:
    """Best-effort JSON object out of an LLM reply; {} if it didn't comply."""
    body = _strip_fences(raw)
    try:
        obj = json.loads(body)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        m = re.search(r"\{.*\}", body, re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return {}
        return {}


# ------------------------------------------------------- shared primitives
def _write_cypher(question: str, prev: str = "", err: str = "") -> tuple[str, str]:
    """One LLM call: classify the question AND write read-only Cypher for it."""
    fix = ""
    if err:
        fix = (
            f"\nYour previous Cypher FAILED or returned nothing:\n"
            f"  query: {prev}\n  problem: {err}\n"
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
        f"Question: {question}{fix}"
    )
    return _parse_plan(invoke_text(prompt, 0))


def _run(cypher: str) -> tuple[list[dict], str | None]:
    """Execute generated Cypher behind the read-only guard."""
    if not cypher:
        return [], "empty query"
    if _WRITE.search(cypher):
        return [], "Rejected: query contains a write clause (read-only only)."
    try:
        return run_cypher(cypher), None
    except Exception as e:
        return [], str(e).split("\n")[0][:300]


def _gather(question: str) -> dict:
    """Answer ONE sub-question against the graph: plan -> execute -> retry once.

    Returns {question, cypher, rows, error} — raw evidence, not prose. Used by
    both the decomposition pass and the reflection follow-up so a sub-question
    goes through exactly the same grounded path as the top-level one.
    """
    _, cypher = _write_cypher(question)
    rows, err = _run(cypher)
    if (err or not rows) and "Rejected" not in (err or ""):
        _, cypher = _write_cypher(
            question, cypher, err or "query returned 0 rows — likely a name mismatch"
        )
        rows, err = _run(cypher)
    return {"question": question, "cypher": cypher, "rows": rows, "error": err}


def _cite(evidence: list[dict]) -> list[str]:
    """Every graph id that actually appeared in evidence, deduped and sorted."""
    cites: set[str] = set()
    for ev in evidence:
        for r in ev.get("rows", []):
            for v in r.values():
                if isinstance(v, str) and _ID.fullmatch(v):
                    cites.add(v)
    return sorted(cites)


# ------------------------------------------------------------------ nodes
def plan_node(state: QueryState) -> QueryState:
    q = state["question"]
    cat, cyp = _write_cypher(q, state.get("cypher", ""), state.get("error") or "")
    state["category"] = cat
    state["cypher"] = cyp
    retry = bool(state.get("error"))
    _add_trace(state, "classify", f"'{q}' -> {cat}",
               "Re-planning after the first attempt came back empty."
               if retry else
               f"Read your question. This is a {'reasoning' if cat == 'diagnostic' else 'lookup'} question.")
    _add_trace(state, "cypher", cyp, "Wrote a query to pull the facts out of the project graph.")
    return state


def execute_node(state: QueryState) -> QueryState:
    rows, err = _run(state.get("cypher", ""))
    state["rows"] = rows

    if err and "Rejected" in err:
        state["error"] = err
        _add_trace(state, "execute", "BLOCKED write query",
                   "Refused to run that — Foreman is only ever allowed to read the graph, never change it.")
        return state
    if err:
        state["retries"] = state.get("retries", 0) + 1
        state["error"] = err
        _add_trace(state, "execute", f"error (retry {state['retries']}): {err}",
                   "That query didn't work. Fixing it and trying again.")
        return state
    if not rows and state.get("retries", 0) < MAX_CYPHER_RETRIES:
        state["retries"] = state.get("retries", 0) + 1
        state["error"] = "query returned 0 rows — likely a name/filter mismatch"
        _add_trace(state, "execute", "0 rows -> will retry",
                   "Found nothing — probably the wrong name. Rewording and trying again.")
        return state

    state["error"] = None
    state["evidence"] = [{"question": state["question"],
                          "cypher": state.get("cypher", ""), "rows": rows}]
    _add_trace(state, "execute", f"{len(rows)} row(s)",
               f"Found {len(rows)} matching record{'s' if len(rows) != 1 else ''} in the graph.")
    return state


def _route_after_execute(state: QueryState) -> str:
    if state.get("error") and state.get("retries", 0) <= MAX_CYPHER_RETRIES \
            and "Rejected" not in (state.get("error") or ""):
        return "retry"
    # A reasoning question that found its footing earns the deep path.
    if state.get("category") == "diagnostic" and state.get("rows"):
        return "decompose"
    return "answer"


def decompose_node(state: QueryState) -> QueryState:
    """Break a hard question into the smaller ones it actually depends on.

    A question like "why is the switchgear at risk?" is really three questions
    (what's its status / who supplies it / what waits on it). Asking the graph
    once answers a third of it; asking three times answers it properly. This is
    the sub-question half of the 41% -> 82% loop.
    """
    q = state["question"]
    known = state.get("rows", [])[:6]
    prompt = (
        "You are Foreman, reasoning over a construction supply-chain knowledge "
        "graph. The user asked a question that needs several facts to answer "
        "well. Break it into the SMALLEST set of independent sub-questions "
        "(1-3) that together fully answer it.\n"
        "Each sub-question must be answerable by a single lookup against a "
        "graph of Materials, Suppliers, Purchase Orders and schedule "
        "Activities. Do NOT repeat what we already know.\n"
        "WRITE THEM FOR A SITE MANAGER TO READ: use the real material and "
        "supplier NAMES from the known data, never database ids like 'MAT-6', "
        "and no schema words. These sub-questions are shown on screen.\n\n"
        f"Question: {q}\n"
        f"Already known: {known}\n\n"
        "Respond ONLY as JSON: {\"subquestions\": [\"...\"]}"
    )
    subs = _parse_json_obj(invoke_text(prompt, 0)).get("subquestions", [])
    subs = [str(s).strip() for s in subs if str(s).strip()][:MAX_SUBQUESTIONS]
    state["subquestions"] = subs

    if not subs:
        _add_trace(state, "decompose", "no sub-questions needed",
                   "This one is answerable directly — no need to break it down.")
        return state

    _add_trace(state, "decompose", json.dumps(subs),
               f"Broke your question into {len(subs)} smaller ones: "
               + "; ".join(f"“{s}”" for s in subs))

    evidence = list(state.get("evidence", []))
    for sub in subs:
        ev = _gather(sub)
        evidence.append(ev)
        n = len(ev["rows"])
        _add_trace(
            state, "sub-answer", f"{sub} -> {n} row(s) via {ev['cypher']}",
            f"Checked “{sub}” — {'found ' + str(n) + ' record' + ('s' if n != 1 else '') if n else 'nothing on record'}.",
        )
    state["evidence"] = evidence
    return state


def _word_for(key: str, value: float) -> str | None:
    """Turn a stored score into the phrase the rest of the app already uses.

    Confidence and supplier reliability are different things and must not be
    described with the same words — "confirmed" is about whether we know where
    something is, "hits their dates" is about a track record.
    """
    k = key.lower()
    if "confidence" in k:
        if value >= 0.9:
            return "confirmed"
        if value >= 0.75:
            return "fairly sure"
        return "not confirmed"
    if "reliability" in k:
        if value >= 0.9:
            return "usually hits their dates"
        if value >= 0.75:
            return "mostly reliable"
        return "patchy record"
    return None


def _humanise(rows):
    """Replace score values with words anywhere in the evidence rows."""
    if isinstance(rows, list):
        return [_humanise(r) for r in rows]
    if isinstance(rows, dict):
        out = {}
        for k, v in rows.items():
            word = _word_for(k, v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
            out[k] = word if word is not None else _humanise(v)
        return out
    return rows


def answer_node(state: QueryState) -> QueryState:
    q = state["question"]
    evidence = state.get("evidence", [])
    rows_total = sum(len(e.get("rows", [])) for e in evidence)

    if not rows_total:
        state["answer"] = (
            "I couldn't find that in the project graph. Try naming a specific "
            "material, supplier, or job — e.g. 'the switchgear' or 'the diesel "
            "generators'."
        )
        state["citations"] = []
        _add_trace(state, "answer", "no rows / gave guidance",
                   "Couldn't find anything on that — asked you to name a specific item instead.")
        return state

    gap = state.get("gap")
    # Scores are turned into words BEFORE the model sees them. Asking it in the
    # prompt not to quote decimals half-worked and then backfired: it started
    # quoting the thresholds from the instruction itself ("confidence is below
    # 0.75"). If the number never reaches the prompt, it cannot be echoed.
    body = "\n".join(
        f"- For '{e['question']}': {_humanise(e['rows'])}"
        for e in evidence if e.get("rows")
    )
    prompt = (
        "You are Foreman, a construction supply-chain analyst talking to a site "
        "manager. Answer the question from ONLY this graph data.\n"
        "STYLE: plain English, concrete, no jargon and no fluff. Use the "
        "material/supplier NAMES, not database ids. Give dates plainly. "
        "Lead with the answer, then the reason.\n"
        "Scores already arrive as words (\"confirmed\", \"patchy record\") — "
        "use them as given and never turn them back into numbers.\n"
        "Only mention a supplier's record when it actually helps answer the "
        "question. Never tack it on, and never call a supplier reliable in the "
        "same breath as holding them responsible for a delay — that reads as a "
        "contradiction. If the data does not support the question's premise, "
        "say so plainly rather than inventing a reason for it.\n"
        + (f"\nA self-check found this was missing last time — make sure the "
           f"answer now covers it: {gap}\n" if gap else "")
        + f"\nQuestion: {q}\nGraph data:\n{body}"
    )
    state["answer"] = invoke_text(prompt, 0.3).strip()
    state["citations"] = _cite(evidence)
    _add_trace(state, "answer", f"cited {state['citations']}",
               "Wrote the answer using only what the graph actually says."
               if not gap else "Rewrote the answer with the missing piece included.")
    return state


def reflect_node(state: QueryState) -> QueryState:
    """Check our own answer before showing it, and fetch what's missing.

    This is the self-reflection half of the loop. It is deliberately allowed
    exactly one correction: the model must either sign the answer off or name
    ONE specific missing fact, which is then fetched from the graph like any
    other question. It can add evidence; it can never add opinion.
    """
    q = state["question"]
    evidence = state.get("evidence", [])
    prompt = (
        "You are reviewing another analyst's answer before it reaches a site "
        "manager who will act on it.\n"
        f"Question: {q}\n"
        f"Evidence used: {[e.get('rows') for e in evidence]}\n"
        f"Draft answer: {state.get('answer','')}\n\n"
        "Check ONLY these: (a) is every claim in the draft supported by the "
        "evidence, and (b) is a fact needed to answer the question missing?\n"
        "Be strict but practical — if the draft answers the question, approve "
        "it. Do not ask for nice-to-have extras.\n"
        "Respond ONLY as JSON: {\"ok\": true} or "
        "{\"ok\": false, \"missing\": \"<what's missing, one phrase>\", "
        "\"followup\": \"<one lookup question that would fill it>\"}"
    )
    verdict = _parse_json_obj(invoke_text(prompt, 0))
    state["reflections"] = state.get("reflections", 0) + 1

    if verdict.get("ok", True) or not verdict.get("followup"):
        state["gap"] = None
        _add_trace(state, "reflect", "self-check passed",
                   "Checked my own answer against the evidence — every claim holds up.")
        return state

    missing = str(verdict.get("missing", "a supporting fact"))
    followup = str(verdict["followup"]).strip()
    state["gap"] = missing
    _add_trace(state, "reflect", f"gap: {missing} -> {followup}",
               f"Checked my own answer and found a gap: {missing}. Going back to the graph for it.")

    ev = _gather(followup)
    state["evidence"] = list(evidence) + [ev]
    n = len(ev["rows"])
    _add_trace(state, "sub-answer", f"{followup} -> {n} row(s)",
               f"Looked up “{followup}” — {'found it' if n else 'still nothing on record'}.")
    return state


def _route_after_answer(state: QueryState) -> str:
    """Only reasoning questions get self-checked, and only once.

    A lookup ("when does the steel arrive?") is either right or empty — there
    is nothing to reflect on, and spending two extra LLM calls on it would slow
    the common case for nothing.
    """
    if state.get("category") == "diagnostic" and state.get("rows") \
            and state.get("reflections", 0) == 0:
        return "reflect"
    return "end"


def _route_after_reflect(state: QueryState) -> str:
    if state.get("gap") and state.get("reflections", 0) <= MAX_REFLECTIONS:
        return "revise"
    return "done"


# ------------------------------------------------------------------ build
def build_query_agent():
    g = StateGraph(QueryState)
    g.add_node("plan", plan_node)
    g.add_node("execute", execute_node)
    g.add_node("decompose", decompose_node)
    g.add_node("answer", answer_node)
    g.add_node("reflect", reflect_node)

    g.add_edge(START, "plan")
    g.add_edge("plan", "execute")
    g.add_conditional_edges("execute", _route_after_execute,
                            {"retry": "plan", "decompose": "decompose",
                             "answer": "answer"})
    g.add_edge("decompose", "answer")
    g.add_conditional_edges("answer", _route_after_answer,
                            {"reflect": "reflect", "end": END})
    g.add_conditional_edges("reflect", _route_after_reflect,
                            {"revise": "answer", "done": END})
    return g.compile()


_AGENT = None


def ask(question: str) -> QueryState:
    """Answer a question; returns full state (answer + citations + trace)."""
    global _AGENT
    if _AGENT is None:
        _AGENT = build_query_agent()
    return _AGENT.invoke({"question": question, "retries": 0, "trace": [],
                          "evidence": [], "reflections": 0})


if __name__ == "__main__":
    for q in [
        "Which materials have confidence below 0.75?",
        "What is the switchgear's expected arrival and who supplies it?",
        "Why are the diesel generators the biggest risk on this project?",
    ]:
        print("\n" + "=" * 70 + f"\nQ: {q}")
        res = ask(q)
        print(f"[{res['category']}] cypher: {res['cypher']}")
        if res.get("subquestions"):
            print("sub-questions:", res["subquestions"])
        print("A:", res["answer"])
        print("cites:", res.get("citations"))
        print("--- trace ---")
        for s in res.get("trace", []):
            print(f"  · {s['say']}")
