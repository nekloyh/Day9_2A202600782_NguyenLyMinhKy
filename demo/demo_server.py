"""Live HTML demo server for Stage 4 multi-agent interactions (Bonus task #1).

Serves a single-page frontend and streams each agent's activity over
Server-Sent Events (SSE) as the LangGraph multi-agent graph executes a
legal question. The browser visualises the pipeline lighting up node by node:

    analyze_law -> check_routing -> [tax + compliance + privacy] -> aggregate

Run:
    uv run python -m demo.demo_server
    # then open http://localhost:8800

Same-origin (HTML served by this app), so no CORS setup is needed.
"""

from __future__ import annotations

import json
import os
import sys
import time

# Allow running as a module or a script from the lab root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

from stages.stage_4_milti_agent.main import create_graph

load_dotenv()

app = FastAPI(title="Multi-Agent Live Demo")
HTML_PATH = os.path.join(os.path.dirname(__file__), "index.html")

# Which state key each node writes — used to pull a human-readable snippet.
NODE_RESULT_KEY = {
    "analyze_law": "law_analysis",
    "call_tax_specialist": "tax_result",
    "call_compliance_specialist": "compliance_result",
    "call_privacy_specialist": "privacy_result",
    "aggregate": "final_answer",
}


def _sse(event: str, data: dict) -> str:
    """Format a Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/")
async def index() -> HTMLResponse:
    with open(HTML_PATH, encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


@app.get("/stream")
async def stream(q: str) -> StreamingResponse:
    """Run the Stage 4 graph and stream per-node updates as SSE."""

    async def gen():
        graph = create_graph()
        inputs = {
            "question": q,
            "law_analysis": "",
            "needs_tax": False,
            "needs_compliance": False,
            "needs_privacy": False,
            "tax_result": "",
            "compliance_result": "",
            "privacy_result": "",
            "final_answer": "",
        }

        t0 = time.perf_counter()
        steps = 0
        workers: list[str] = []
        yield _sse("start", {"question": q})

        try:
            async for chunk in graph.astream(inputs, stream_mode="updates"):
                for node, update in chunk.items():
                    steps += 1

                    if node == "check_routing":
                        nxt = []
                        if update.get("needs_tax"):
                            nxt.append("call_tax_specialist")
                        if update.get("needs_compliance"):
                            nxt.append("call_compliance_specialist")
                        if update.get("needs_privacy"):
                            nxt.append("call_privacy_specialist")
                        text = (
                            f"needs_tax={update.get('needs_tax')}, "
                            f"needs_compliance={update.get('needs_compliance')}, "
                            f"needs_privacy={update.get('needs_privacy')}\n"
                            f"→ dispatch song song: {', '.join(nxt) or 'none'}"
                        )
                        yield _sse("node", {"node": node, "text": text, "next": nxt})
                        continue

                    if node == "aggregate":
                        text = update.get("final_answer", "")
                        yield _sse("final", {"text": text})
                        continue

                    key = NODE_RESULT_KEY.get(node)
                    text = update.get(key, "") if key else json.dumps(update, ensure_ascii=False)
                    if node in ("call_tax_specialist", "call_compliance_specialist", "call_privacy_specialist"):
                        workers.append(node.replace("call_", "").replace("_specialist", ""))
                    yield _sse("node", {"node": node, "text": text, "next": []})

            latency = round(time.perf_counter() - t0, 2)
            yield _sse("done", {"nodes": steps, "latency": latency, "workers": workers})
        except Exception as exc:  # surface backend errors to the browser
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(gen(), media_type="text/event-stream")


if __name__ == "__main__":
    port = int(os.getenv("DEMO_PORT", "8800"))
    print(f"Multi-Agent demo running at http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
