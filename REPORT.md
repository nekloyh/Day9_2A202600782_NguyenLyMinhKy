# Báo Cáo Lab: Multi-Agent, MCP & A2A Systems
**Môn học:** AI20K — D09  
**Ngày thực hiện:** 06/09/2025  
**Họ tên:** Nguyễn Lý Minh Kỳ
**MSSV:** 2A202600782

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
Starting Tax Agent on port 10102...
Starting Compliance Agent on port 10103...
Starting Law Agent on port 10101...
Starting Customer Agent on port 10100...

All services started:
  Registry:         http://localhost:10000
  Customer Agent:   http://localhost:10100
  Law Agent:        http://localhost:10101
  Tax Agent:        http://localhost:10102
  Compliance Agent: http://localhost:10103
```

### Bước 2: Kiểm Tra Registry

```bash
curl http://localhost:10000/agents | python -m json.tool
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
When a company breaches a contract and engages in tax evasion, it faces significant legal and regulatory consequences. Here’s a comprehensive overview of the implications under both contract law and tax law:

### 1. Breach of Contract

**Legal Principles**:
- A breach occurs when one party fails to fulfill its contractual obligations. The non-breaching party can seek remedies such as:
  - **Damages**: This includes compensatory damages to cover lost profits and consequential damages that were foreseeable at the time of the contract.
  - **Specific Performance**: Courts may order the breaching party to fulfill its obligations under the contract.
  - **Rescission**: The contract may be voided, releasing both parties from their obligations.

**Relevant Statutes and Case Law**:
- The Uniform Commercial Code (UCC) governs contracts for the sale of goods, while common law applies to other agreements. Notable cases, like *Hadley v. Baxendale*, establish rules for consequential damages.

### 2. Tax Evasion

**Legal Principles**:
- Tax evasion is a criminal offense involving the deliberate misrepresentation of information to reduce tax liability, such as underreporting income or inflating deductions.

**Consequences**:
- **Criminal Penalties**: Under federal law, tax evasion can lead to felony charges, with fines reaching up to $100,000 for individuals and $500,000 for corporations, plus potential imprisonment.
- **Civil Penalties**: The IRS may impose fines and interest on unpaid taxes, increasing the financial burden.
- **Audit and Investigation**: Engaging in tax evasion can trigger an IRS audit, leading to further scrutiny.

### 3. Liability Exposure

**Corporate Liability**:
- The company may face:
  - **Contractual Liability**: For damages due to the breach.
  - **Tax Liability**: For back taxes, penalties, and interest.
  - **Reputational Damage**: Tax evasion can harm the company’s reputation, affecting business and investor confidence.

**Personal Liability**:
- Executives or board members may face personal liability, especially if they were involved in the misconduct.

### 4. Regulatory Consequences

**Regulatory Oversight**:
- Regulatory bodies like the IRS and the SEC may investigate, leading to fines and sanctions. State tax authorities may also impose penalties.

### 5. Mitigating Factors

**Voluntary Disclosure and Cooperation**:
- Voluntarily disclosing breaches or tax issues can mitigate penalties. Cooperation with investigations may also reduce liability.

**Compliance Programs**:
- Implementing compliance programs can demonstrate a commitment to preventing misconduct, which may help in reducing liability.

### Conclusion
In summary, a company that breaches a contract while engaging in tax evasion faces serious legal and regulatory consequences, including civil and criminal penalties, liability for damages, and reputational harm. It is crucial for companies to adhere to contractual obligations and comply with tax laws to mitigate these risks. Consulting with legal counsel is advisable for navigating these complex issues.

**Disclaimer**: This response is for educational purposes only and should not be construed as legal advice. Please consult a licensed attorney for specific legal guidance tailored to your situation.
============================================================
```

### Bài Tập 5.1: Trace Request Flow

**Trace ID tìm được trong logs:** `trace_id=f329d283-fb5f-40d2-9300-20bcba9dcffa`

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
17:24:26 [customer_agent] CustomerAgent executing | task=7243814e trace=f329d283 depth=0
17:24:26 [customer_agent] CustomerAgent direct-delegate | trace=f329d283 depth=0
17:24:26 [customer_agent] GET http://localhost:10000/discover/legal_question → 200 OK
17:24:26 [customer_agent] GET http://localhost:10101/.well-known/agent.json → 200 OK
          ── Law Agent xử lý (analyze_law + check_routing + parallel) ──
17:24:54 [tax_agent]      TaxAgent executing | trace=f329d283 depth=2
17:24:58 [tax_agent]      POST https://api.openai.com/v1/chat/completions → 200 OK
17:25:20 [customer_agent] POST http://localhost:10101 → 200 OK  [kết quả về]
```

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

**Nhận xét quan trọng:** Hệ thống **không crash** — `call_tax()` trong `law_agent/graph.py:152` bắt exception và trả về fallback string. Law Agent vẫn tổng hợp kết quả với phần tax bị thiếu. Đây là graceful degradation — ưu điểm lớn của kiến trúc distributed so với in-process.

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
• Criminal penalty: up to 5 years imprisonment and a $250,000 fine per count (26 U.S.C. § 7201).
• Jurisdiction: IRS (civil audit/collection), DOJ Tax Division (criminal prosecution), FinCEN (AML/BSA violations).
• Statute of limitations: 6 years for substantial omission (IRC § 6501(e)), unlimited for fraudulent returns.

⚠️ Educational purposes only — consult a licensed tax attorney for specific advice.
```

---

## Câu Hỏi Ôn Tập

**1. Khi nào nên dùng single agent thay vì multi-agent?**

Dùng single agent khi: (a) domain bài toán hẹp và đồng nhất, (b) không cần parallel processing, (c) latency là ưu tiên (overhead giao tiếp giữa agents tốn thêm 1-3s mỗi hop), (d) team nhỏ và muốn giữ codebase đơn giản. Multi-agent phù hợp khi bài toán cần nhiều chuyên môn khác nhau, hoặc các subtask có thể chạy độc lập song song.

**2. Ưu điểm của A2A protocol so với gRPC hoặc REST thông thường?**

A2A chuẩn hóa khái niệm "agent" với Agent Card (`/.well-known/agent.json`) — client tự discover capabilities mà không cần đọc documentation. Protocol hỗ trợ native Task lifecycle (submitted → working → completed/failed), streaming, và multi-turn conversations. Ngược lại, gRPC/REST thuần túy yêu cầu mỗi team tự định nghĩa interface schema, không có convention về agent capabilities hay task state.

**3. Làm thế nào để prevent infinite delegation loops trong A2A?**

Code trong lab dùng `delegation_depth` — mỗi hop tăng lên 1, Law Agent kiểm tra `if depth >= MAX_DELEGATION_DEPTH` (=3) và bỏ qua sub-delegation nếu đã quá sâu (`law_agent/graph.py:77-80`). Ngoài ra có thể dùng: circuit breaker pattern, explicit allow-list của agents được phép gọi nhau, hoặc trace-based loop detection (phát hiện cùng `trace_id` quay lại agent đã xử lý).

**4. Tại sao cần Registry service? Có thể hardcode URLs không?**

Hardcode URLs được nhưng tạo tight coupling: khi scale (nhiều instance Tax Agent), hoặc deploy lên Kubernetes (pod IPs thay đổi), phải update config mọi agent. Registry cung cấp dynamic discovery — agents register on startup, clients discover by task name. Nếu một agent scale thành 3 replicas, Registry có thể load balance; nếu agent offline, Registry trả 404 thay vì connection refused không rõ ràng. Trong production, có thể dùng Consul, etcd, hoặc Kubernetes Service DNS thay cho custom registry.

---

## Bài Tập Cộng Điểm

### Đo Latency Hệ Thống (Stage 5)

**Phương pháp đo:** Thêm `time.perf_counter()` vào `test_client.py` bao quanh lệnh `send_message`:

```python
t0 = time.perf_counter()
response = await client.send_message(request)
elapsed = time.perf_counter() - t0
print(f"\n⏱  Total latency: {elapsed:.2f}s")
```

**Breakdown thực tế từ logs (run đo live):**
```
CustomerAgent direct-delegate bắt đầu:   17:24:26.616
  └─ discover + fetch law_agent card:    +0.05s
  └─ Law Agent analyze_law (LLM):        │
  └─ Law Agent check_routing (LLM):      │  28.1s tổng cộng
  └─ Tax Agent nhận request:             17:24:54.782
     └─ Tax Agent LLM (concise prompt):  3.6s
  └─ Compliance Agent (song song):       ~22s (ước tính)
  └─ Law Agent aggregate (LLM):          ~5s (ước tính)
CustomerAgent nhận kết quả:              17:25:20.661
─────────────────────────────────────────────────────
Tổng đo được:                            54.05s
Customer Agent LLM calls:               0  ✓ (xác nhận từ logs)
Tax Agent LLM calls:                     1  ✓ (concise prompt)
```

> **Lưu ý về variance:** OpenAI API latency biến động lớn. Run 1 đo được 35.89s, run 2 đo được 54.05s với cùng code — mức dao động bình thường khi dùng public LLM API.

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
[customer_agent] CustomerAgent direct-delegate | trace=f329d283 depth=0
# (không có thêm LLM call nào)
```

**Tiết kiệm:** 2 LLM calls × ~3-5s/call = **~6-10s** mỗi request (ngoài ra còn giảm cost API).

**Phương án bổ sung (tiềm năng giảm thêm):**

| Phương án | Latency giảm ước tính | Độ phức tạp |
|---|---|---|
| Bỏ LLM ở Customer Agent **(đã demo, đã apply)** | 6-10s | Thấp |
| Dùng model nhỏ hơn (e.g. gpt-4o-mini) cho `analyze_law` + `aggregate` | ~40% | Thấp |
| Streaming response — user thấy output ngay khi có | Perceived latency giảm mạnh | Thấp |
| Semantic cache cho câu hỏi giống nhau | ~100% nếu cache hit | Trung bình |
| Bỏ `aggregate` LLM, concat trực tiếp các section | ~5s (giảm quality) | Thấp |

---

## So Sánh 5 Stages

| Stage | Pattern | Latency đo được | Fault Tolerance | Scalability |
|---|---|---|---|---|
| 1 | Direct LLM | ~1-2s | N/A | Stateless, dễ scale |
| 2 | LLM + Tools | ~2-5s | Tool error = partial result | Stateless |
| 3 | ReAct Agent | ~5-10s | Retry tự động | Stateless |
| 4 | Multi-Agent In-Process | ~20-35s | Một agent crash → cả hệ thống crash | Scale cả cụm |
| 5 | Distributed A2A (optimized) | **35-55s** (đo live) | Graceful degradation | Scale từng service độc lập |

> Latency Stage 5 biến động lớn (35-55s) do phụ thuộc vào OpenAI API response time — không phải do kiến trúc. Với self-hosted LLM, latency sẽ ổn định hơn nhiều.

**Kết luận:** Latency tăng theo độ phức tạp nhưng đổi lại là fault-tolerance và scalability thực sự. Stage 5 phù hợp cho production; tối ưu latency nên tập trung vào LLM selection (model nhỏ hơn / self-hosted) hơn là thay đổi kiến trúc.

---

## Kết Luận

Lab này cho thấy sự đánh đổi rõ ràng giữa simplicity và robustness khi xây dựng hệ thống AI. Kiến trúc A2A phân tán (Stage 5) phức tạp hơn nhiều so với gọi LLM trực tiếp (Stage 1), nhưng mang lại khả năng mở rộng và chịu lỗi mà các ứng dụng production thực sự cần. Bài học quan trọng nhất: **chọn kiến trúc phù hợp với yêu cầu thực tế**, không phải kiến trúc phức tạp nhất có thể.
