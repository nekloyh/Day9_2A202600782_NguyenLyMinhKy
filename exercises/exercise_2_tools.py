"""Bài Tập 2: Thêm tools và knowledge base đã hoàn chỉnh."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from common.llm import get_llm

# Knowledge base
LEGAL_KNOWLEDGE = [
    {
        "id": "ucc_breach",
        "keywords": ["breach", "contract", "remedies", "damages", "ucc"],
        "text": (
            "Under the Uniform Commercial Code (UCC) Article 2, remedies for breach of contract "
            "include: (1) expectation damages; (2) consequential damages; (3) specific performance; "
            "(4) cover damages. Statute of limitations is typically 4 years (UCC § 2-725)."
        ),
    },
    {
        "id": "labor_law",
        "keywords": ["lao", "động", "sa", "thải", "labor", "termination", "employment"],
        "text": (
            "Theo Bộ luật Lao động Việt Nam 2019, người sử dụng lao động có thể "
            "đơn phương chấm dứt hợp đồng trong các trường hợp: (1) người lao động "
            "thường xuyên không hoàn thành công việc; (2) bị ốm đau, tai nạn đã điều trị "
            "12 tháng chưa khỏi; (3) thiên tai, hỏa hoạn; (4) người lao động đủ tuổi nghỉ hưu. "
            "Thời hiệu khởi kiện tranh chấp lao động cá nhân: 1 năm; tập thể: 3 năm."
        ),
    },
]


@tool
def search_legal_knowledge(query: str) -> str:
    """Tìm kiếm trong knowledge base pháp lý. Trả về tối đa 2 kết quả liên quan nhất."""
    query_words = set(query.lower().split())
    scored = []
    for entry in LEGAL_KNOWLEDGE:
        overlap = len(query_words & set(entry["keywords"]))
        if overlap > 0:
            scored.append((overlap, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:2]
    if not top:
        return "Không tìm thấy thông tin liên quan."
    return "\n\n".join(f"[{e['id']}] {e['text']}" for _, e in top)


@tool
def check_statute_of_limitations(case_type: str) -> str:
    """Kiểm tra thời hiệu khởi kiện theo loại vụ án (Việt Nam và Hoa Kỳ).

    Args:
        case_type: Loại vụ án bằng tiếng Anh. Các giá trị hợp lệ:
                   contract, tort, property, labor, fraud, ip, defamation,
                   personal_injury, criminal
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
    matched = key if key in limits else next(
        (k for k in limits if key in k or k in key), None
    )

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


async def main():
    load_dotenv()
    llm = get_llm()
    
    tools = [search_legal_knowledge, check_statute_of_limitations]
    llm_with_tools = llm.bind_tools(tools)
    tool_map = {tool.name: tool for tool in tools}
    
    question = "Thời hiệu khởi kiện vụ vi phạm hợp đồng là bao lâu?"
    
    messages = [
        SystemMessage(content="Bạn là chuyên gia pháp lý. Sử dụng tools để tra cứu thông tin."),
        HumanMessage(content=question),
    ]
    
    print(f"Câu hỏi: {question}\n")
    
    # First LLM call - decide which tools to use
    response = await llm_with_tools.ainvoke(messages)
    messages.append(response)
    
    # Execute tools if requested
    if response.tool_calls:
        for tool_call in response.tool_calls:
            print(f"🔧 Gọi tool: {tool_call['name']}")
            selected_tool = tool_map.get(tool_call["name"])
            if selected_tool is None:
                tool_result = f"Tool không được hỗ trợ: {tool_call['name']}"
            else:
                tool_result = selected_tool.invoke(tool_call["args"])

            messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))
        
        # Second LLM call - synthesize final answer
        final_response = await llm_with_tools.ainvoke(messages)
        print(f"\n✅ Kết quả:\n{final_response.content}")
    else:
        print(f"\n✅ Kết quả:\n{response.content}")


if __name__ == "__main__":
    asyncio.run(main())
