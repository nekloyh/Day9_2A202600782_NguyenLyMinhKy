"""Lab Assignment — Supervisor-Workers multi-agent legal advisor.

Improves the Day08 RAG agent into a LangGraph Supervisor-Workers system:
a supervisor LLM dynamically routes to specialist workers (legal_research,
tax, compliance) one at a time until the question is fully covered.
"""

from .supervisor import create_graph

__all__ = ["create_graph"]
