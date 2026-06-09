"""Tax Agent LangGraph definition.

Uses create_react_agent with a tax-specialised system prompt.
No tools — it answers purely from LLM knowledge.
"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from common.llm import get_llm

TAX_SYSTEM_PROMPT = """You are a specialist tax attorney and CPA. Answer CONCISELY using EXACTLY 5 bullet points.

Format each bullet as: • [Key point] — [Brief explanation with specific statute/penalty if applicable]

Cover these areas in order:
1. Whether the conduct is civil or criminal (cite the statute)
2. Civil penalty amount and basis (e.g., IRC § 6663)
3. Criminal penalty — imprisonment term and fine
4. Which government agency has jurisdiction (IRS, DOJ, FinCEN)
5. Statute of limitations and any mitigating options

Rules:
- One sentence per bullet, no sub-bullets, no headers
- Always cite specific IRC sections or U.S.C. statutes
- Distinguish company liability from individual executive liability where relevant

End with one line: "⚠️ Educational purposes only — consult a licensed tax attorney for specific advice."
"""


def create_graph():
    """Return a compiled LangGraph create_react_agent for tax questions."""
    llm = get_llm()
    graph = create_react_agent(
        model=llm,
        tools=[],
        prompt=TAX_SYSTEM_PROMPT,
    )
    return graph