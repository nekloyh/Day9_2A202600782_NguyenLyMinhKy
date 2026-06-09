# Lab Assignment — Supervisor-Workers Multi-Agent

**Họ tên:** Nguyễn Lý Minh Kỳ — **MSSV:** 2A202600782

Cải thiện agent (Day08 RAG → Day09 Multi-Agent) bằng pattern **Supervisor – Workers**
với **3 workers** chuyên môn, dùng LangGraph.

## Pattern: Supervisor – Workers

Một **supervisor** (LLM) đứng giữa, mỗi lượt nhìn xem worker nào đã chạy rồi
**động** quyết định worker kế tiếp nên hành động — hoặc `FINISH`. Worker luôn
trả quyền điều khiển về supervisor, tạo thành vòng lặp `supervisor ↔ worker`.

```
        ┌───────────────────────────────────────────┐
        ▼                                            │
    supervisor ──route──► legal_research ────────────┤
        │             ├──► tax ───────────────────────┤
        │             └──► compliance ────────────────┘
        │
        └──FINISH──► synthesize ──► END
```

### 3 Workers
| Worker | Vai trò |
|---|---|
| `legal_research` | RAG: truy xuất knowledge base → viết research brief có trích nguồn (kế thừa Day08 RAG) |
| `tax` | Chuyên gia thuế (IRS, IRC §§ 6651/6662/6663, FBAR/FATCA, 26 U.S.C. § 7201) |
| `compliance` | Tuân thủ + quyền riêng tư (SEC, SOX, FCPA, GDPR, CCPA, Nghị định 13/2023) |

## Khác biệt với Stage 4 (router tĩnh)

| | Stage 4 / law_agent | Lab Assignment (Supervisor-Workers) |
|---|---|---|
| Định tuyến | Tĩnh: 1 lần `check_routing` rồi fan-out parallel `Send` | **Động**: supervisor quyết định từng lượt, có thể đổi hướng |
| Luồng | analyze → route → parallel → aggregate (một chiều) | Vòng lặp `supervisor ↔ worker` tới khi FINISH |
| Phối hợp | Các specialist chạy độc lập, song song | Worker sau **đọc output** worker trước (legal_research làm nền cho tax/compliance) |
| An toàn | `MAX_DELEGATION_DEPTH` | `MAX_ITERATIONS` guard chống loop vô hạn |

## Chạy

```bash
# Từ thư mục lab/ (cần .env có OPENAI_API_KEY)
uv run python -m Lab_Assignment.main

# Câu hỏi tùy chỉnh
uv run python -m Lab_Assignment.main "Một công ty vi phạm NDA và trốn thuế thì hậu quả pháp lý là gì?"
```

Output gồm: **routing trace** (chuỗi quyết định của supervisor), **final answer**
tổng hợp, và số liệu (workers engaged, supervisor turns, latency).

## Cấu trúc

```
Lab_Assignment/
├── __init__.py     # export create_graph
├── state.py        # SupervisorState (shared state + reducers)
├── workers.py      # 3 worker nodes + RAG knowledge base
├── supervisor.py   # supervisor node, routing, synthesize, graph builder
├── main.py         # entry point + smoke test
└── README.md
```
