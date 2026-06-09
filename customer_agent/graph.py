"""Customer Agent LangGraph definition.

Direct-delegation design: bypasses LLM routing entirely and forwards the
user question straight to the Law Agent via A2A.  This removes ~2 LLM round
trips (routing decision + response reformatting) and cuts end-to-end latency
by ~5-8 seconds compared to the original create_react_agent approach.

Trace context (trace_id, context_id, depth) is bound per-request via closure
in the same way as before, so observability is unaffected.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import MessagesState

logger = logging.getLogger(__name__)


def build_graph(trace_id: str, context_id: str, depth: int) -> Any:
    """Build a direct-delegation graph — no LLM in the hot path.

    Args:
        trace_id: UUID generated at this request's entry point.
        context_id: A2A context_id for this conversation.
        depth: Delegation depth (0 at customer agent).

    Returns:
        A compiled LangGraph graph.
    """

    async def delegate_node(state: MessagesState) -> dict:
        """Forward the last user message to the Law Agent and return the result."""
        from common.a2a_client import delegate
        from common.registry_client import discover

        question = state["messages"][-1].content
        logger.info(
            "CustomerAgent direct-delegate | trace=%s context=%s depth=%d",
            trace_id, context_id, depth,
        )
        try:
            endpoint = await discover("legal_question")
            result = await delegate(
                endpoint=endpoint,
                question=question,
                context_id=context_id,
                trace_id=trace_id,
                depth=depth + 1,
            )
            if not result:
                result = "The Law Agent returned an empty response. Please try again."
        except Exception as exc:
            logger.exception("direct-delegate failed: %s", exc)
            result = f"Could not reach the Law Agent: {exc}"

        return {"messages": [AIMessage(content=result)]}

    graph = StateGraph(MessagesState)
    graph.add_node("delegate", delegate_node)
    graph.set_entry_point("delegate")
    graph.add_edge("delegate", END)
    return graph.compile()