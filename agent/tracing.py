"""
agent/tracing.py
Structured JSON trace logging per node/tool call (timestamp, input/output
summary, latency, cost) -- Phase 6. cost_usd is always 0.0 on the local
Ollama backend; the field exists so switching LLM_BACKEND=claude later has
somewhere real to report actual per-call cost.
"""
import json
import os
import time
from typing import Callable

from pydantic import BaseModel


class TraceEvent(BaseModel):
    node: str
    start_ts: float
    end_ts: float
    latency_sec: float
    input_summary: str
    output_summary: str
    cost_usd: float = 0.0
    error: str | None = None


def traced(node_name: str, describe_input: Callable[[dict], str], describe_output: Callable[[dict], str]):
    """Decorator for a LangGraph node function: records a TraceEvent into
    state["trace"] around the call. Nodes mutate and return the same state
    dict, so describe_input reads pre-call state and describe_output reads
    the post-call (mutated) state."""

    def decorator(fn):
        def wrapper(state: dict) -> dict:
            start = time.time()
            input_summary = describe_input(state)
            new_state = fn(state)
            end = time.time()
            event = TraceEvent(
                node=node_name,
                start_ts=start,
                end_ts=end,
                latency_sec=round(end - start, 3),
                input_summary=input_summary,
                output_summary=describe_output(new_state),
            )
            new_state.setdefault("trace", []).append(event.model_dump())
            return new_state

        return wrapper

    return decorator


def save_trace(state: dict, out_dir: str = "traces") -> str:
    """Writes this run's full trace to a timestamped JSON file for the
    dashboard to read. Returns the file path."""
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(out_dir, f"run-{ts}.json")
    with open(path, "w") as f:
        json.dump({
            "question": state["question"],
            "final_output": state["final_output"],
            "retry_count": state.get("retry_count", 0),
            "critic_verdict": state["critic_result"].verdict if state.get("critic_result") else None,
            "trace": state.get("trace", []),
        }, f, indent=2, default=str)
    return path
