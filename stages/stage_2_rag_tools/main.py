"""Stage 2: LLM + RAG / Tools

Adds retrieval-augmented generation and tool use to ground LLM responses
in external data. The LLM can now search a legal knowledge base and
calculate damages — but the orchestration is manual (one tool-call loop).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from common.llm import get_llm

# ---------------------------------------------------------------------------
# Simulated legal knowledge base (in production, this would be a vector store)
# ---------------------------------------------------------------------------

LEGAL_KNOWLEDGE = [
    {
        "id": "ucc_breach",
        "keywords": ["breach", "contract", "remedies", "damages", "ucc"],
        "text": (
            "Under the Uniform Commercial Code (UCC) Article 2, remedies for breach of contract "
            "include: (1) expectation damages — placing the non-breaching party in the position "
            "they would have been in had the contract been performed; (2) consequential damages "
            "for foreseeable losses (Hadley v. Baxendale, 1854); (3) specific performance when "
            "the subject matter is unique; (4) cover damages — the cost of obtaining substitute "
            "performance. The statute of limitations is typically 4 years (UCC § 2-725)."
        ),
    },
    {
        "id": "nda_trade_secret",
        "keywords": ["nda", "non-disclosure", "confidential", "trade secret", "agreement"],
        "text": (
            "NDA breaches may trigger both contractual and statutory liability. Under the Defend "
            "Trade Secrets Act (DTSA, 18 U.S.C. § 1836), misappropriation of trade secrets can "
            "result in: (1) injunctive relief; (2) actual damages plus unjust enrichment; "
            "(3) exemplary damages up to 2x actual damages for willful misappropriation; "
            "(4) attorney's fees. State Uniform Trade Secrets Act (UTSA) versions provide "
            "additional remedies. Criminal prosecution is possible under the Economic Espionage "
            "Act (18 U.S.C. § 1832) with penalties up to $5M for individuals."
        ),
    },
    {
        "id": "dtsa_details",
        "keywords": ["dtsa", "federal", "trade secret", "defend", "statute"],
        "text": (
            "The Defend Trade Secrets Act (2016) created a federal private cause of action for "
            "trade secret misappropriation. Key provisions: (1) ex parte seizure orders in "
            "extraordinary circumstances; (2) 3-year statute of limitations; (3) immunity for "
            "whistleblower disclosures to government officials; (4) employers must notify "
            "employees of whistleblower immunity in any NDA or employment agreement."
        ),
    },
    {
        "id": "liquidated_damages",
        "keywords": ["liquidated", "damages", "penalty", "clause", "contract", "nda"],
        "text": (
            "Liquidated damages clauses in NDAs are enforceable if: (1) actual damages would be "
            "difficult to calculate at the time of contracting; (2) the stipulated amount is a "
            "reasonable estimate of anticipated harm. Courts will void clauses that function as "
            "penalties (Restatement (Second) of Contracts § 356). Typical NDA liquidated damages "
            "range from $10,000 to $500,000 depending on the nature of the confidential information."
        ),
    },
    {
        "id": "injunctive_relief",
        "keywords": ["injunction", "restraining", "order", "equitable", "nda", "breach"],
        "text": (
            "Courts routinely grant temporary restraining orders (TROs) and preliminary injunctions "
            "for NDA breaches because: (1) confidential information, once disclosed, cannot be "
            "'un-disclosed' — making monetary damages inadequate; (2) irreparable harm is presumed "
            "for trade secret misappropriation in many jurisdictions. The movant must show "
            "likelihood of success on the merits, irreparable harm, balance of equities, and "
            "public interest (Winter v. Natural Resources Defense Council, 2008)."
        ),
    },
    {
        "id": "labor_law",
        "keywords": ["lao động", "sa thải", "hợp đồng lao động", "labor", "termination"],
        "text": (
            "Theo Bộ luật Lao động Việt Nam 2019, người sử dụng lao động có thể "
            "đơn phương chấm dứt hợp đồng trong các trường hợp: (1) người lao động "
            "thường xuyên không hoàn thành công việc; (2) bị ốm đau, tai nạn đã điều trị "
            "12 tháng chưa khỏi; (3) thiên tai, hỏa hoạn; (4) người lao động đủ tuổi nghỉ hưu."
        ),
    }
]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def search_legal_database(query: str) -> str:
    """Search the legal knowledge base for relevant statutes, case law, and legal principles."""
    query_words = set(query.lower().split())
    scored = []
    for entry in LEGAL_KNOWLEDGE:
        overlap = len(query_words & set(entry["keywords"]))
        if overlap > 0:
            scored.append((overlap, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:2]
    if not top:
        return "No relevant legal sources found for this query."
    results = []
    for _, entry in top:
        results.append(f"[{entry['id']}] {entry['text']}")
    return "\n\n".join(results)


@tool
def calculate_damages(breach_type: str, contract_value: float) -> str:
    """Calculate estimated damages for a contract breach based on type and contract value."""
    breach_type_lower = breach_type.lower()
    if "willful" in breach_type_lower or "intentional" in breach_type_lower:
        multiplier = 2.0
        label = "Willful/intentional breach (2x multiplier under DTSA)"
    elif "negligent" in breach_type_lower:
        multiplier = 1.0
        label = "Negligent breach (1x actual damages)"
    else:
        multiplier = 1.5
        label = "Standard breach (1.5x estimated multiplier)"

    base_damages = contract_value * multiplier
    attorney_fees = contract_value * 0.15
    total = base_damages + attorney_fees

    return (
        f"Damage Estimate:\n"
        f"  Breach type: {label}\n"
        f"  Contract value: ${contract_value:,.2f}\n"
        f"  Estimated damages: ${base_damages:,.2f}\n"
        f"  Attorney's fees (~15%): ${attorney_fees:,.2f}\n"
        f"  Total estimated exposure: ${total:,.2f}"
    )


@tool
def check_statute_of_limitations(case_type: str) -> str:
    """Kiểm tra thời hiệu khởi kiện theo loại vụ án (Việt Nam và Hoa Kỳ).

    Args:
        case_type: Loại vụ án. Ví dụ: contract, tort, property, nda, labor,
                   fraud, ip, defamation, personal_injury, criminal
    """
    limits = {
        "contract": {
            "vn": "3 năm (Bộ luật Dân sự 2015, Điều 429)",
            "us": "4 năm (UCC § 2-725); 6 năm ở một số bang (NY, MA)",
            "note": "Tính từ ngày biết hoặc phải biết quyền bị vi phạm",
        },
        "tort": {
            "vn": "3 năm (BLDS 2015, Điều 588)",
            "us": "2-3 năm tùy bang",
            "note": "Tính từ ngày xảy ra hành vi gây thiệt hại hoặc ngày phát hiện",
        },
        "property": {
            "vn": "Không thời hạn với tranh chấp quyền sở hữu; 3 năm với thiệt hại tài sản",
            "us": "3-10 năm tùy bang và loại bất động sản",
            "note": "Tranh chấp quyền sở hữu đất đai VN không áp dụng thời hiệu",
        },
        "nda": {
            "vn": "3 năm (BLDS 2015, áp dụng theo hợp đồng)",
            "us": "3 năm (DTSA, 18 U.S.C. § 1836(d))",
            "note": "Tính từ ngày phát hiện hoặc lẽ ra phải phát hiện hành vi vi phạm",
        },
        "labor": {
            "vn": "1 năm tranh chấp cá nhân; 3 năm tranh chấp tập thể (Bộ luật LĐ 2019)",
            "us": "180-300 ngày (EEOC filing); 2-3 năm cho FLSA claims",
            "note": "VN: tính từ ngày phát hiện hành vi vi phạm quyền lợi lao động",
        },
        "fraud": {
            "vn": "3 năm (BLDS 2015); hình sự tùy khung hình phạt",
            "us": "2-6 năm tùy bang; discovery rule thường áp dụng",
            "note": "Nhiều bang áp dụng discovery rule: tính từ khi phát hiện gian lận",
        },
        "ip": {
            "vn": "2 năm (Luật SHTT 2005, sửa đổi 2022)",
            "us": "3 năm bản quyền (17 U.S.C. § 507); 6 năm nhãn hiệu (Lanham Act)",
            "note": "Tính từ ngày phát hiện hành vi xâm phạm quyền SHTT",
        },
        "defamation": {
            "vn": "3 năm (BLDS 2015, Điều 588)",
            "us": "1-3 năm tùy bang; thường 1 năm",
            "note": "Một trong những thời hiệu ngắn nhất trong luật dân sự Mỹ",
        },
        "personal_injury": {
            "vn": "3 năm (BLDS 2015, Điều 588)",
            "us": "2-3 năm tùy bang",
            "note": "Discovery rule áp dụng khi thiệt hại không phát hiện ngay",
        },
        "criminal": {
            "vn": "5-20 năm tùy khung hình phạt (BLTTHS 2015, Điều 27); tội đặc biệt nghiêm trọng không có thời hiệu",
            "us": "5 năm liên bang (18 U.S.C. § 3282); murder và một số tội không có thời hiệu",
            "note": "VN: tội có mức hình phạt tử hình không áp dụng thời hiệu truy cứu",
        },
    }

    key = case_type.lower().strip()
    matched = None
    if key in limits:
        matched = key
    else:
        for k in limits:
            if key in k or k in key:
                matched = k
                break

    if matched is None:
        available = ", ".join(limits.keys())
        return (
            f"Không tìm thấy thời hiệu cho loại vụ án '{case_type}'. "
            f"Các loại được hỗ trợ: {available}"
        )

    entry = limits[matched]
    return (
        f"Thời hiệu khởi kiện — {matched.upper()}\n"
        f"  Việt Nam : {entry['vn']}\n"
        f"  Hoa Kỳ   : {entry['us']}\n"
        f"  Lưu ý    : {entry['note']}"
    )


TOOLS = [search_legal_database, calculate_damages, check_statute_of_limitations]

QUESTION = "Hậu quả pháp lý là gì nếu một công ty vi phạm thỏa thuận bảo mật NDA Việt Nam?"

async def main():
    print("=" * 70)
    print("STAGE 2: LLM + RAG / Tools")
    print("=" * 70)
    print()
    print("[How it works]")
    print("  1. LLM receives tools (search_legal_database, calculate_damages)")
    print("  2. LLM decides which tools to call and with what arguments")
    print("  3. We execute the tools and feed results back to the LLM")
    print("  4. LLM generates a final answer grounded in retrieved data")
    print()
    print(f"Question: {QUESTION}")
    print("-" * 70)

    llm = get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)
    tool_map = {t.name: t for t in TOOLS}

    messages = [
        SystemMessage(
            content=(
                "You are a legal expert with access to a legal knowledge base and a damage "
                "calculator. Use the tools provided to ground your analysis in specific statutes "
                "and case law. Always search the database before answering. "
                "Keep your final response under 400 words."
            )
        ),
        HumanMessage(content=QUESTION),
    ]

    # --- Step 1: LLM decides which tools to call ---
    print("\n>>> Step 1: Asking LLM (with tools bound)...\n")
    response = await llm_with_tools.ainvoke(messages)
    messages.append(response)

    if not response.tool_calls:
        print("LLM chose not to use any tools. Direct answer:")
        print(response.content)
        return
    else:
        print("LLM decided to use tools. Proceeding to execute tool calls...\n")

    # --- Step 2: Execute tool calls ---
    print(f">>> Step 2: LLM requested {len(response.tool_calls)} tool call(s):\n")
    for tc in response.tool_calls:
        print(f"  Tool: {tc['name']}")
        print(f"  Args: {tc['args']}")

        tool_fn = tool_map[tc["name"]]
        result = await tool_fn.ainvoke(tc["args"])
        print(f"  Result: {result[:200]}{'...' if len(result) > 200 else ''}")
        print()

        messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

    # --- Step 3: LLM generates final grounded answer ---
    print(">>> Step 3: LLM generating final answer with tool results...\n")
    final_response = await llm_with_tools.ainvoke(messages)
    print(final_response.content)

    print()
    print("-" * 70)
    print("[Improvements over Stage 1]")
    print("  + Grounded: answers cite specific statutes (DTSA, UCC, etc.)")
    print("  + Tool use: can search databases and calculate damages")
    print("  + More accurate: retrieval reduces hallucination risk")
    print()
    print("[Limitations of Stage 2]")
    print("  - Manual orchestration: we wrote the tool-call loop ourselves")
    print("  - Single pass: only one round of tool calls")
    print("  - No reasoning loop: LLM can't decide to search again if needed")
    print()
    print("Next: Stage 3 wraps this in an autonomous ReAct agent loop.")
    print("=" * 70)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())