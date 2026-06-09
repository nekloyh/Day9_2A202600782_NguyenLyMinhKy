# Báo Cáo Lab: Multi-Agent, MCP & A2A Systems
**Môn học:** AI20K — D09<br>
**Ngày thực hiện:** 06/09/2025<br>
**Ngày kiểm chứng gần nhất:** 09/06/2026<br>
**Họ tên:** Nguyễn Lý Minh Kỳ<br>
**MSSV:** 2A202600782<br>
**LLM:** OpenAI API, mặc định `gpt-4o-mini`, `temperature=0.3`

## Tổng Quan Kết Quả

| Phần | Nội dung | Trạng thái |
|---|---|---|
| 1 | Direct LLM, đổi câu hỏi, temperature control | Hoàn thành |
| 2 | Labor-law knowledge và statute-of-limitations tool | Hoàn thành |
| 3 | ReAct agent và case-law tool | Hoàn thành |
| 4 | Privacy agent, conditional routing, parallel `Send` | Hoàn thành |
| 5 | Distributed A2A, discovery, tracing, graceful degradation | Hoàn thành |
| Cộng điểm | Đo và tối ưu latency | Hoàn thành |

### Phần 1–4: Các Thay Đổi Chính

- **Phần 1:** đổi câu hỏi pháp lý trong `stages/stage_1_direct_llm/main.py`; cấu hình `temperature=0.3` trong `common/llm.py`.
- **Phần 2:** thêm entry `labor_law`, tool `check_statute_of_limitations`, bind tool và thực thi qua tool map. Cả Stage 2 và `exercises/exercise_2_tools.py` đã hoàn chỉnh.
- **Phần 3:** thêm `search_case_law` vào danh sách tools; bật LangChain debug để quan sát ReAct loop.
- **Phần 4:** thêm privacy specialist, conditional routing theo `data/privacy/gdpr/dữ liệu`, aggregation và edge về node tổng hợp. `exercises/exercise_4_multiagent.py` đã được kiểm chứng bằng một lượt `graph.ainvoke()` với fake LLM.

## Phần 5: Distributed A2A System

**Kiến trúc:**
```
Registry (10000)  ← agents tự đăng ký khi startup
       ↓
Customer Agent (10100)  ← entry point
       ↓  discover("legal_question")
 Law Agent (10101)      ← orchestrator
       ↓  parallel Send
   ┌───┴───────────────────┐
Tax (10102)       Compliance (10103)
   └───┬───────────────────┘
       ↓  aggregate
  Final Answer
```

**Trace propagation:** `trace_id` được tạo tại Customer Agent và truyền qua `message.metadata` qua toàn bộ chuỗi gọi — cho phép debug và observability.

### Bước 1: Khởi Động Hệ Thống

```bash
./start_all.sh
```

**Output:**
```
Starting Registry service on port 10000...
Registry is ready.
Starting Tax Agent on port 10102...
Starting Compliance Agent on port 10103...
Tax Agent is ready.
Compliance Agent is ready.
Starting Law Agent on port 10101...
Law Agent is ready.
Starting Customer Agent on port 10100...
Customer Agent is ready.

All services started:
  Registry:         http://localhost:10000
  Customer Agent:   http://localhost:10100
  Law Agent:        http://localhost:10101
  Tax Agent:        http://localhost:10102
  Compliance Agent: http://localhost:10103
```

### Bước 2: Kiểm Tra Registry

```bash
curl -sS http://localhost:10000/agents | uv run python -m json.tool
```

**Output (4 agents đã đăng ký):**
```json
{
  "agents": [
    {"agent_name": "customer-agent", "endpoint": "http://localhost:10100", ...},
    {"agent_name": "law-agent",      "endpoint": "http://localhost:10101", "tasks": ["legal_question"]},
    {"agent_name": "tax-agent",      "endpoint": "http://localhost:10102", "tasks": ["tax_question"]},
    {"agent_name": "compliance-agent","endpoint": "http://localhost:10103", "tasks": ["compliance_question"]}
  ]
}
```

### Bước 3: Chạy Test Client

```bash
uv run python test_client.py
```

**Output:**
```
Connecting to Customer Agent at http://localhost:10100
Question: If a company breaks a contract and avoids taxes, what are the legal
          and regulatory consequences?
------------------------------------------------------------
Connected to agent: Customer Agent v1.0.0
------------------------------------------------------------
Sending request (this may take 30-60s while agents chain)...

RESPONSE:
============================================================
# Comprehensive Legal Analysis: Breach of Contract and Tax Avoidance

## 1. Breach of Contract
- Phân tích remedies, damages, specific performance và rescission.

## 2. Tax Consequences
- Phân biệt tax avoidance hợp pháp với tax evasion bất hợp pháp.
- Nêu civil penalties, criminal exposure và thẩm quyền của IRS/DOJ.

## 3. Regulatory and Individual Liability
- Phân tích SEC/regulatory scrutiny, trách nhiệm của công ty và cá nhân quản lý.

## 4. Mitigating Factors
- Voluntary disclosure, cooperation, remediation và compliance programs.

**Disclaimer**: Educational purposes only; consult licensed attorneys.
============================================================

⏱  Total latency: 32.35s
```

Kết quả trên được chạy live ngày **09/06/2026**. Nội dung chi tiết thay đổi giữa các lần gọi LLM, nhưng cấu trúc delegation và các specialist tham gia được xác nhận qua logs.

### Bài Tập 5.1: Trace Request Flow

**Trace ID của lần kiểm chứng gần nhất:** `trace_id=cc092912-2b50-483b-88e9-8879eff6467a`

**Sequence Diagram** *(Customer Agent dùng direct-delegation — không có LLM call)*:
```
test_client.py       CustomerAgent (direct)        LawAgent         TaxAgent    ComplianceAgent
     │                       │                         │                │              │
     │──POST /──────────────>│                         │                │              │
     │                       │──GET /discover/───────>Registry          │              │
     │                       │<──endpoint:10101────────│                │              │
     │                       │──POST / (A2A)──────────>│                │              │
     │                  [no LLM]                        │──analyze_law──>OpenAI         │
     │                       │                         │<──law_analysis──│              │
     │                       │                         │──check_routing─>OpenAI         │
     │                       │                         │──GET /discover/─>Registry      │
     │                       │                         │──GET /discover/──────────────>Registry
     │                       │                         │──POST /────────>│    [parallel] │
     │                       │                         │──POST /──────────────────────>│
     │                       │                         │<── tax_result ──│              │
     │                       │                         │<── compliance_result ──────────│
     │                       │                         │──aggregate─────>OpenAI         │
     │                       │<──final_answer──────────│                │              │
     │<──Task(artifacts)─────│                         │                │              │
```

**Log thực tế (run đo latency):**
```
19:51:45.132 [customer_agent] CustomerAgent executing | trace=cc092912 depth=0
19:51:45.134 [customer_agent] CustomerAgent direct-delegate | trace=cc092912 depth=0
19:51:45.141 [registry]       discover/legal_question → law-agent
19:51:45.146 [customer_agent] GET law-agent/.well-known/agent-card.json → 200
19:51:45.146 [law_agent]      LawAgent executing | trace=cc092912 depth=1
19:51:55.459 [law_agent]      analyze_law OpenAI call → 200
19:51:56.380 [law_agent]      check_routing OpenAI call → 200
19:51:56.381 [law_agent]      needs_tax=True, needs_compliance=True
19:51:56.401 [tax_agent]      TaxAgent executing | trace=cc092912 depth=2
19:51:56.402 [compliance]     ComplianceAgent executing | trace=cc092912 depth=2
19:51:59.351 [tax_agent]      OpenAI call → 200
19:52:05.909 [compliance]     OpenAI call → 200
19:52:17.472 [law_agent]      aggregate OpenAI call → 200
19:52:17.474 [customer_agent] Law Agent response → 200
```

Tax và Compliance bắt đầu cách nhau khoảng **1 ms**, xác nhận hai nhánh được dispatch song song bằng LangGraph `Send`.

### Bài Tập 5.2: Test Dynamic Discovery (Fault Tolerance)

**Dừng Tax Agent:**
```bash
pkill -f "tax_agent"
```

**Chạy lại test_client.py — kết quả:**
```
## Tax Analysis
[Tax analysis unavailable: Connection refused to http://localhost:10102]
```

**Nhận xét quan trọng:** Hệ thống **không crash** — `call_tax()` bắt exception và trả về fallback string `[Tax analysis unavailable: ...]`. Law Agent vẫn tổng hợp kết quả với phần tax bị thiếu. Registry hiện dùng in-memory store và chưa có heartbeat/deregistration, nên vẫn có thể trả endpoint của agent vừa dừng; lỗi kết nối được xử lý tại Law Agent. Đây là graceful degradation ở tầng orchestrator, chưa phải service discovery có health awareness.

### Bài Tập 5.3: Modify Tax Agent Behavior

**Sửa `tax_agent/graph.py` — thay prompt dài bằng prompt ngắn gọn có cấu trúc:**

```python
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
```

**Restart chỉ Tax Agent:**
```bash
uv run python -m tax_agent
```

**Kết quả trước (prompt gốc):** ~1800 chars, nhiều đoạn văn, không có cite statute cụ thể  
**Kết quả sau (prompt mới) — xác nhận từ log thực tế (1 LLM call, ~3.6s):**
```
• Tax evasion is both civil and criminal — governed by 26 U.S.C. § 7201 (felony) and IRC § 6663 (civil fraud).
• Civil penalty: 75% of the underpayment attributable to fraud (IRC § 6663), plus interest under IRC § 6601.
• Criminal penalty: up to 5 years imprisonment; § 7201 provides up to $100,000 for an individual or $500,000 for a corporation, while 18 U.S.C. § 3571 may raise the individual maximum to $250,000.
• Jurisdiction: IRS (civil audit/collection), DOJ Tax Division (criminal prosecution), FinCEN (AML/BSA violations).
• Limitation periods: generally 6 years for specified criminal tax offenses under § 6531; civil assessment may be made at any time for a fraudulent return under § 6501(c).

⚠️ Educational purposes only — consult a licensed tax attorney for specific advice.
```

Nguồn kiểm tra cho các con số pháp lý: [26 U.S.C. § 7201](https://uscode.house.gov/quicksearch/get.plx?section=7201&title=26), [26 U.S.C. § 6501](https://uscode.house.gov/quicksearch/get.plx?section=6501&title=26), [26 U.S.C. § 6531](https://uscode.house.gov/view.xhtml?req=%28title%3A26+section%3A6531+edition%3Aprelim%29), và [IRS Criminal Statutory Provisions](https://www.irs.gov/irm/part9/irm_09-001-003).

---

## Câu Hỏi Ôn Tập

**1. Khi nào nên dùng single agent thay vì multi-agent?**

Dùng single agent khi: (a) domain bài toán hẹp và đồng nhất, (b) không cần parallel processing, (c) latency là ưu tiên (overhead giao tiếp giữa agents tốn thêm 1-3s mỗi hop), (d) team nhỏ và muốn giữ codebase đơn giản. Multi-agent phù hợp khi bài toán cần nhiều chuyên môn khác nhau, hoặc các subtask có thể chạy độc lập song song.

**2. Ưu điểm của A2A protocol so với gRPC hoặc REST thông thường?**

A2A chuẩn hóa khái niệm "agent" với Agent Card (`/.well-known/agent-card.json`) — client có thể discover capabilities và transport metadata theo convention chung. Protocol hỗ trợ Task lifecycle, streaming và multi-turn context. Ngược lại, gRPC/REST thuần túy chỉ cung cấp transport/interface primitives; mỗi hệ thống phải tự định nghĩa semantics cho agent capability, task state và message exchange.

**3. Làm thế nào để prevent infinite delegation loops trong A2A?**

Code trong lab dùng `delegation_depth` — mỗi hop tăng lên 1, Law Agent kiểm tra `if depth >= MAX_DELEGATION_DEPTH` (=3) và bỏ qua sub-delegation nếu đã quá sâu. Ngoài ra có thể dùng circuit breaker, explicit allow-list của agents được phép gọi nhau, hoặc trace-based loop detection.

**4. Tại sao cần Registry service? Có thể hardcode URLs không?**

Hardcode URLs được nhưng tạo tight coupling: khi endpoint thay đổi, phải cập nhật cấu hình ở các caller. Registry trong lab cung cấp dynamic discovery theo task: agents register khi startup và clients lookup endpoint tại runtime. Bản hiện tại trả agent đầu tiên khớp task, chưa có load balancing, heartbeat hoặc tự loại bỏ instance offline. Trong production có thể mở rộng Registry hoặc dùng Consul, etcd hay Kubernetes Service DNS.

---

## Bài Tập Cộng Điểm

### Đo Latency Hệ Thống (Stage 5)

**Phương pháp đo:** dùng `time.perf_counter()` trong `test_client.py` bao quanh toàn bộ vòng lặp nhận event từ A2A client:

```python
t0 = time.perf_counter()
response = None
async for event in client.send_message(message):
    response = event[0] if isinstance(event, tuple) else event
elapsed = time.perf_counter() - t0
print(f"\n⏱  Total latency: {elapsed:.2f}s")
```

**Breakdown thực tế từ logs ngày 09/06/2026:**
```
CustomerAgent bắt đầu:                   19:51:45.132
  └─ discover + fetch Law Agent card:    ~0.01s
  └─ Law Agent analyze_law:              ~10.31s
  └─ Law Agent check_routing:            ~0.92s
  └─ Tax + Compliance bắt đầu song song: 19:51:56.401/402
     ├─ Tax Agent hoàn thành:            ~2.95s
     └─ Compliance Agent hoàn thành:     ~9.51s
  └─ Law Agent aggregate:                ~11.56s
CustomerAgent nhận kết quả:              19:52:17.474
─────────────────────────────────────────────────────
Tổng đo được:                            32.35s
Customer Agent LLM calls:               0  ✓ (xác nhận từ logs)
Tax Agent LLM calls:                     1  ✓ (concise prompt)
Compliance Agent LLM calls:              1  ✓
```

Một lượt live test khác cùng ngày đo được **36.76s**. Trung bình hai lượt kiểm chứng gần nhất là **34.56s**. OpenAI API latency có thể biến động giữa các lần chạy.

### Demo Tối Ưu: Bỏ LLM ở Customer Agent

**Vấn đề:** Customer Agent gốc dùng `create_react_agent` — LLM phải *quyết định* gọi tool và sau đó *reformat* response, tốn 2 LLM calls thừa vì Customer Agent **luôn luôn** delegate 100% câu hỏi.

**Giải pháp — `customer_agent/graph.py` thay bằng Direct Delegation:**

```python
async def delegate_node(state: MessagesState) -> dict:
    question = state["messages"][-1].content
    endpoint = await discover("legal_question")
    result = await delegate(endpoint=endpoint, question=question,
                            context_id=context_id, trace_id=trace_id, depth=depth + 1)
    return {"messages": [AIMessage(content=result)]}

graph = StateGraph(MessagesState)
graph.add_node("delegate", delegate_node)
graph.set_entry_point("delegate")
graph.add_edge("delegate", END)
```

**Kết quả — xác nhận từ logs:**
```
# TRƯỚC (create_react_agent):
[customer_agent] Customer delegate_to_legal_agent | trace=... depth=0
[customer_agent] POST https://api.openai.com/v1/chat/completions → 200 OK   ← LLM call #1 (routing)
[customer_agent] POST https://api.openai.com/v1/chat/completions → 200 OK   ← LLM call #2 (reformat)

# SAU (direct delegation):
[customer_agent] CustomerAgent direct-delegate | trace=cc092912 depth=0
# (không có thêm LLM call nào)
```

**Tiết kiệm ước tính:** bỏ 2 LLM round trips ở Customer Agent, tương đương khoảng **5-8s** tùy latency của model, đồng thời giảm API cost.

**Phương án bổ sung (tiềm năng giảm thêm):**

| Phương án | Latency giảm ước tính | Độ phức tạp |
|---|---|---|
| Bỏ LLM ở Customer Agent **(đã demo, đã apply)** | Khoảng 5-8s | Thấp |
| Dùng model nhỏ/nhanh hơn cho routing và aggregation | Phụ thuộc model | Thấp |
| Streaming response — user thấy output ngay khi có | Perceived latency giảm mạnh | Thấp |
| Semantic cache cho câu hỏi giống nhau | ~100% nếu cache hit | Trung bình |
| Bỏ `aggregate` LLM, concat trực tiếp các section | Giảm một LLM call, đổi lại giảm chất lượng | Thấp |

---

## So Sánh 5 Stages

| Stage | Pattern | Latency | Fault Tolerance | Scalability |
|---|---|---|---|---|
| 1 | Direct LLM | Chưa benchmark trong lần kiểm chứng này | LLM failure làm request thất bại | Stateless |
| 2 | LLM + Tools | Chưa benchmark trong lần kiểm chứng này | Chưa có retry/tool fallback tổng quát | Stateless |
| 3 | ReAct Agent | Chưa benchmark trong lần kiểm chứng này | Tool/LLM failure có thể dừng run | Stateless |
| 4 | Multi-Agent In-Process | Chưa benchmark trong lần kiểm chứng này | Một node lỗi có thể làm graph thất bại | Scale cả process |
| 5 | Distributed A2A (optimized) | **32.35s và 36.76s** (live) | Specialist failure có fallback | Có thể scale từng service sau khi bổ sung discovery/load balancing phù hợp |

> Chỉ Stage 5 được benchmark lại trong phiên kiểm chứng ngày 09/06/2026. Không nên trình bày latency của Stage 1–4 như số đo nếu chưa chạy benchmark tương ứng.

**Kết luận:** Stage 5 chứng minh được service separation, tracing, dynamic lookup và graceful degradation. Tuy nhiên đây vẫn là demo/learning architecture: Registry và task store còn in-memory, chưa có authentication, persistence, heartbeat, retry policy hay production-grade load balancing.

---

## Kết Luận

Lab này cho thấy sự đánh đổi giữa simplicity, latency và isolation khi xây dựng hệ thống AI. Kiến trúc A2A phân tán phức tạp hơn direct LLM nhưng cho phép tách service, truyền trace context và xử lý fallback theo từng specialist. Để đưa lên production vẫn cần bổ sung persistence, authentication, health-aware discovery, retries/circuit breakers và monitoring. Bài học chính là **chọn kiến trúc phù hợp với yêu cầu thực tế**, không mặc định chọn kiến trúc phức tạp nhất.
