"""Worker agents for the Supervisor-Workers pattern.

Three specialist workers, each focused on one legal domain:

  - legal_research : RAG-style grounding. Retrieves from a knowledge base
                     first (carrying over the Day08 RAG idea), then writes a
                     grounded research brief. Other workers build on this.
  - tax            : tax-law specialist (IRS, IRC, FBAR/FATCA).
  - compliance     : regulatory compliance specialist (SEC, SOX, GDPR, CCPA).

Every worker writes its analysis into `worker_outputs[<name>]`, logs itself in
`history`, increments `iterations`, and returns control to the supervisor.
"""

from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from common.llm import get_llm

from .state import SupervisorState

logger = logging.getLogger(__name__)

# Worker name constants — shared with the supervisor so routing stays in sync.
LEGAL_RESEARCH = "legal_research"
TAX = "tax"
COMPLIANCE = "compliance"
WORKERS = [LEGAL_RESEARCH, TAX, COMPLIANCE]


# ---------------------------------------------------------------------------
# Knowledge base (RAG grounding — carried over from the Day08 RAG pipeline)
# ---------------------------------------------------------------------------

LEGAL_KNOWLEDGE = [
    {
        "id": "nda_breach",
        "keywords": ["nda", "non-disclosure", "confidential", "trade", "secret", "breach"],
        "text": (
            "NDA breaches trigger contractual and statutory liability. Under the DTSA "
            "(18 U.S.C. § 1836): injunctive relief, actual damages + unjust enrichment, "
            "exemplary damages up to 2x for willful misappropriation, and attorney's fees."
        ),
    },
    {
        "id": "contract_remedies",
        "keywords": ["breach", "contract", "remedies", "damages", "ucc"],
        "text": (
            "UCC Article 2 remedies: expectation damages, consequential damages (Hadley v. "
            "Baxendale), specific performance for unique goods, cover damages. Statute of "
            "limitations: 4 years (UCC § 2-725)."
        ),
    },
    {
        "id": "tax_evasion",
        "keywords": ["tax", "evasion", "irs", "penalty", "fraud", "revenue", "thuế"],
        "text": (
            "Tax evasion (26 U.S.C. § 7201): felony, up to $250K fine and 5 years prison. "
            "Civil fraud penalty: 75% of underpayment (IRC § 6663). IRS can assess back taxes "
            "+ interest for 6 years (unlimited for fraud)."
        ),
    },
    {
        "id": "data_privacy",
        "keywords": ["data", "privacy", "user", "consent", "gdpr", "ccpa", "dữ", "liệu"],
        "text": (
            "Sharing user data without consent violates: CCPA (up to $7,500 per intentional "
            "violation), GDPR (up to 4% of global revenue or EUR 20M), FTC Act Section 5. "
            "Private right of action under CCPA for breaches ($100-$750 per consumer)."
        ),
    },
    {
        "id": "sox_compliance",
        "keywords": ["sox", "sarbanes", "compliance", "sec", "financial", "reporting"],
        "text": (
            "SOX violations: false CEO/CFO certification — up to $5M fine and 20 years prison "
            "(§ 906). Record destruction — up to 20 years (§ 802). Whistleblower retaliation — "
            "up to 10 years (§ 1107). SEC can bar individuals from officer/director roles."
        ),
    },
]


def retrieve(query: str, top_k: int = 3) -> str:
    """Lexical keyword retrieval over the legal knowledge base (RAG step)."""
    query_words = set(query.lower().split())
    scored = []
    for entry in LEGAL_KNOWLEDGE:
        overlap = len(query_words & set(entry["keywords"]))
        if overlap > 0:
            scored.append((overlap, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]
    if not top:
        return "No relevant legal sources found in the knowledge base."
    return "\n\n".join(f"[{e['id']}] {e['text']}" for _, e in top)


# ---------------------------------------------------------------------------
# Worker node implementations
# ---------------------------------------------------------------------------

async def legal_research_worker(state: SupervisorState) -> dict:
    """RAG-grounded research worker — retrieves sources, then writes a brief."""
    print("    [worker:legal_research] retrieving sources + drafting research brief...")
    question = state["question"]
    retrieved = retrieve(question)

    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "You are a legal research analyst. Using ONLY the retrieved sources below, "
                "write a concise, grounded research brief (under 180 words) identifying the "
                "relevant statutes, legal principles, and exposure. Cite source ids in [brackets]. "
                "If a source is irrelevant, ignore it.\n\n"
                f"=== Retrieved sources ===\n{retrieved}"
            )
        ),
        HumanMessage(content=question),
    ]
    result = await llm.ainvoke(messages)
    logger.info("legal_research_worker produced %d chars", len(result.content))
    return {
        "worker_outputs": {LEGAL_RESEARCH: result.content},
        "history": [LEGAL_RESEARCH],
        "iterations": state["iterations"] + 1,
    }


async def tax_worker(state: SupervisorState) -> dict:
    """Tax-law specialist worker."""
    print("    [worker:tax] analysing tax exposure...")
    research = state["worker_outputs"].get(LEGAL_RESEARCH, "")
    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "You are a specialist tax attorney and CPA (IRS enforcement, IRC §§ 6651/6662/6663, "
                "FBAR/FATCA, tax fraud under 26 U.S.C. § 7201). Analyse the tax exposure for the "
                "question, citing specific statutes. Keep it under 160 words. Build on the research "
                "brief if provided; do not repeat non-tax content."
                + (f"\n\n=== Research brief ===\n{research}" if research else "")
            )
        ),
        HumanMessage(content=state["question"]),
    ]
    result = await llm.ainvoke(messages)
    logger.info("tax_worker produced %d chars", len(result.content))
    return {
        "worker_outputs": {TAX: result.content},
        "history": [TAX],
        "iterations": state["iterations"] + 1,
    }


async def compliance_worker(state: SupervisorState) -> dict:
    """Regulatory compliance + data privacy specialist worker."""
    print("    [worker:compliance] analysing regulatory + privacy exposure...")
    research = state["worker_outputs"].get(LEGAL_RESEARCH, "")
    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "You are a senior regulatory compliance officer (SEC, SOX, FTC, FCPA, AML/BSA, "
                "GDPR, CCPA, Vietnam Decree 13/2023). Analyse the regulatory and data-privacy "
                "exposure for the question, citing specific frameworks and fines. Keep it under "
                "160 words. Build on the research brief if provided; do not repeat non-compliance content."
                + (f"\n\n=== Research brief ===\n{research}" if research else "")
            )
        ),
        HumanMessage(content=state["question"]),
    ]
    result = await llm.ainvoke(messages)
    logger.info("compliance_worker produced %d chars", len(result.content))
    return {
        "worker_outputs": {COMPLIANCE: result.content},
        "history": [COMPLIANCE],
        "iterations": state["iterations"] + 1,
    }


# Map worker name -> node function (consumed by the graph builder).
WORKER_NODES = {
    LEGAL_RESEARCH: legal_research_worker,
    TAX: tax_worker,
    COMPLIANCE: compliance_worker,
}
