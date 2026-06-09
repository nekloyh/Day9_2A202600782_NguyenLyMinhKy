"""Supervisor node + graph construction for the Supervisor-Workers pattern.

Topology:

        ┌────────────────────────────────────────────┐
        │                                             │
        ▼                                             │
    supervisor ──► (route) ──► legal_research ────────┤
        │                ├────► tax ──────────────────┤
        │                └────► compliance ───────────┘
        │
        └──► (FINISH) ──► synthesize ──► END

The supervisor is an LLM that, on each turn, looks at which workers have
already produced output and decides which worker should act next — or FINISH.
Workers always return control to the supervisor, so routing is *dynamic*
(decided per-turn by the LLM), unlike the static fan-out router in Stage 4.

A hard `MAX_ITERATIONS` guard prevents infinite supervisor↔worker loops,
mirroring the MAX_DELEGATION_DEPTH safeguard in the A2A law agent.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from common.llm import get_llm

from .state import SupervisorState
from .workers import WORKER_NODES, WORKERS

logger = logging.getLogger(__name__)

FINISH = "FINISH"
MAX_ITERATIONS = 6  # safety guard: at most this many supervisor decisions


# ---------------------------------------------------------------------------
# Supervisor node
# ---------------------------------------------------------------------------

async def supervisor_node(state: SupervisorState) -> dict:
    """Decide which worker acts next, or FINISH.

    Reads the set of workers that have already produced output and asks the
    LLM to pick the next worker (or FINISH when enough analysis is gathered).
    Falls back to deterministic routing if the LLM reply is unparseable or the
    iteration guard trips.
    """
    done = list(state["worker_outputs"].keys())
    remaining = [w for w in WORKERS if w not in done]
    iterations = state["iterations"]

    # Guard: stop if we've looped too long or every worker has run.
    if iterations >= MAX_ITERATIONS or not remaining:
        decision = FINISH
        print(f"  [supervisor] guard/complete → FINISH (done={done}, iter={iterations})")
        return {"next": decision, "history": [f"supervisor→{decision}"]}

    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "You are the SUPERVISOR of a team of legal worker agents. Your job is to route "
                "the question to the worker best suited to act NEXT, one at a time, until the "
                "question is fully covered — then reply FINISH.\n\n"
                "Available workers:\n"
                "  - legal_research : retrieves statutes/case-law and writes a grounded brief. "
                "Almost always run this FIRST.\n"
                "  - tax            : tax-law exposure (IRS, IRC, evasion, FBAR/FATCA).\n"
                "  - compliance     : regulatory + data-privacy exposure (SEC, SOX, GDPR, CCPA).\n\n"
                "Pick FINISH once the relevant workers have contributed. Do NOT pick a worker "
                "that has already produced output. Only route to tax/compliance if the question "
                "actually involves those domains.\n\n"
                "Reply with ONLY valid JSON, no markdown:\n"
                '{"next": "<legal_research|tax|compliance|FINISH>", "reason": "<short>"}'
            )
        ),
        HumanMessage(
            content=(
                f"Question: {state['question']}\n\n"
                f"Workers already done: {done or 'none'}\n"
                f"Workers still available: {remaining}"
            )
        ),
    ]
    result = await llm.ainvoke(messages)
    raw = result.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
        decision = parsed.get("next", "").strip()
        reason = parsed.get("reason", "")
    except json.JSONDecodeError:
        logger.warning("Supervisor returned non-JSON: %r — falling back", raw)
        decision, reason = "", "unparseable LLM reply"

    # Validate the decision; fall back to the next undone worker, else FINISH.
    if decision not in WORKERS and decision != FINISH:
        decision = remaining[0] if remaining else FINISH
        reason = reason or "fallback to next available worker"
    if decision in done:
        decision = remaining[0] if remaining else FINISH

    print(f"  [supervisor] decision={decision} ({reason}) | done={done} iter={iterations}")
    return {"next": decision, "history": [f"supervisor→{decision}"]}


def route_from_supervisor(state: SupervisorState) -> str:
    """Conditional edge: map the supervisor's decision to the next node."""
    decision = state["next"]
    return "synthesize" if decision == FINISH else decision


# ---------------------------------------------------------------------------
# Synthesis node (runs once after FINISH)
# ---------------------------------------------------------------------------

async def synthesize_node(state: SupervisorState) -> dict:
    """Combine all worker outputs into a single comprehensive answer."""
    print("  [synthesize] combining worker analyses into final answer...")
    outputs = state["worker_outputs"]

    labels = {
        "legal_research": "Legal Research",
        "tax": "Tax Analysis",
        "compliance": "Regulatory & Privacy Analysis",
    }
    sections = [
        f"## {labels.get(name, name)}\n{text}"
        for name, text in outputs.items()
        if text
    ]
    combined = "\n\n---\n\n".join(sections)

    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "You are senior legal counsel synthesising your team's specialist analyses into "
                "one cohesive, well-structured client answer with clear sections. Remove "
                "redundancy. End with a one-line disclaimer that this is educational and the "
                "client should consult a licensed attorney. Keep it under 450 words."
            )
        ),
        HumanMessage(content=combined or state["question"]),
    ]
    result = await llm.ainvoke(messages)
    return {"final_answer": result.content}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def create_graph():
    """Build and compile the Supervisor-Workers StateGraph."""
    graph = StateGraph(SupervisorState)

    graph.add_node("supervisor", supervisor_node)
    for name, fn in WORKER_NODES.items():
        graph.add_node(name, fn)
    graph.add_node("synthesize", synthesize_node)

    graph.set_entry_point("supervisor")

    # Supervisor routes to a worker or to synthesize (on FINISH).
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {**{w: w for w in WORKERS}, "synthesize": "synthesize"},
    )

    # Every worker returns control to the supervisor (the loop).
    for name in WORKER_NODES:
        graph.add_edge(name, "supervisor")

    graph.add_edge("synthesize", END)

    return graph.compile()
