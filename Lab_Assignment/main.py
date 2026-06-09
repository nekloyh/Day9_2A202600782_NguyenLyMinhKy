"""Entry point + smoke test for the Supervisor-Workers legal advisor.

Run:
    uv run python -m Lab_Assignment.main
    uv run python -m Lab_Assignment.main "your custom question here"

The supervisor dynamically routes the question to specialist workers
(legal_research → tax / compliance) until it decides FINISH, then a
synthesis node produces the final client-facing answer.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

# Allow `python Lab_Assignment/main.py` as well as `-m Lab_Assignment.main`.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

from Lab_Assignment.supervisor import MAX_ITERATIONS, create_graph

DEFAULT_QUESTION = (
    "A tech startup with $5M revenue shared user data without consent and also "
    "failed to pay taxes on overseas revenue. What are all the legal consequences?"
)


async def run(question: str) -> dict:
    """Run one question through the Supervisor-Workers graph and return the state."""
    graph = create_graph()
    initial = {
        "question": question,
        "next": "",
        "worker_outputs": {},
        "history": [],
        "iterations": 0,
        "final_answer": "",
    }
    return await graph.ainvoke(initial)


async def main():
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION

    print("=" * 70)
    print("LAB ASSIGNMENT: Supervisor-Workers Legal Advisor")
    print("=" * 70)
    print()
    print("[Pattern] A supervisor LLM dynamically routes to specialist workers")
    print("          (legal_research, tax, compliance) one at a time, looping")
    print(f"          until FINISH (max {MAX_ITERATIONS} supervisor turns).")
    print()
    print(f"Question: {question}")
    print("-" * 70)
    print("\n>>> Running graph...\n")

    t0 = time.perf_counter()
    result = await run(question)
    elapsed = time.perf_counter() - t0

    print("\n" + "=" * 70)
    print("ROUTING TRACE")
    print("=" * 70)
    for step in result["history"]:
        print(f"  {step}")

    print("\n" + "=" * 70)
    print("FINAL ANSWER")
    print("=" * 70)
    print(result["final_answer"])

    print()
    print("-" * 70)
    workers_used = list(result["worker_outputs"].keys())
    print(f"Workers engaged : {workers_used} ({len(workers_used)} of 3)")
    print(f"Supervisor turns: {result['iterations']} worker dispatches")
    print(f"Total latency   : {elapsed:.2f}s")
    print("=" * 70)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
