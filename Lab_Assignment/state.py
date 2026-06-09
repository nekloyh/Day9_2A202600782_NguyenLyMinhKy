"""Shared state for the Supervisor-Workers legal advisory system.

The supervisor reads `worker_outputs` to know which workers have already
produced an analysis, then writes `next` to route control to the next worker
(or to FINISH). Workers append their analysis to `worker_outputs` and log
their name in `history`, then return control to the supervisor.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


def _merge_outputs(left: dict, right: dict) -> dict:
    """Reducer: merge worker output dicts (right overrides on key clash)."""
    merged = dict(left)
    merged.update(right)
    return merged


class SupervisorState(TypedDict):
    """State passed between the supervisor and worker nodes.

    Attributes:
        question:       The original user question.
        next:           Supervisor's routing decision — a worker name or "FINISH".
        worker_outputs: Map of worker name -> analysis text (accumulated).
        history:        Ordered log of routing decisions (for tracing).
        iterations:     Supervisor decision count — guards against infinite loops.
        final_answer:   Synthesised final response produced after FINISH.
    """

    question: str
    next: str
    worker_outputs: Annotated[dict, _merge_outputs]
    history: Annotated[list, operator.add]
    iterations: int
    final_answer: str
