"""
agent/orchestrator.py
Executes the Planner's steps concurrently via asyncio.gather -- mirrors the
production async batch fan-out pattern (independent tool calls run in
parallel rather than sequentially). Each individual tool call gets its own
trace event (not just the orchestrator node as a whole), since that's the
granularity the observability dashboard needs to show real per-tool latency.
"""
import asyncio
import time

from agent.schemas import AgentState, PlanStep, ToolResult
from agent.tools.findocgpt_tool import call_findocgpt
from agent.tracing import TraceEvent


async def _run_step(step: PlanStep, trace: list[dict]) -> ToolResult:
    start = time.time()
    error = None
    try:
        if step.tool == "findocgpt":
            output = await call_findocgpt(step.tool_input)
            result = ToolResult(step=step, output=output)
        else:
            raise ValueError(f"Unknown tool: {step.tool}")
    except Exception as e:
        # A failed tool call shouldn't crash the whole run -- surface it as a
        # result with an error field so downstream nodes (self-critic) can
        # decide whether to retry or fall back to insufficient-info.
        from agent.schemas import FinDocGPTToolResponse
        error = str(e)
        result = ToolResult(step=step, output=FinDocGPTToolResponse(answer="", sources=[]), error=error)

    end = time.time()
    trace.append(TraceEvent(
        node=f"tool:{step.tool}",
        start_ts=start,
        end_ts=end,
        latency_sec=round(end - start, 3),
        input_summary=step.tool_input,
        output_summary=result.output.answer if not error else "",
        error=error,
    ).model_dump())
    return result


async def _run_all(steps: list[PlanStep], trace: list[dict]) -> list[ToolResult]:
    # Appending to `trace` from concurrent coroutines is safe here: asyncio
    # only switches tasks at await points, and list.append is atomic between them.
    return await asyncio.gather(*[_run_step(s, trace) for s in steps])


async def orchestrator_node(state: AgentState) -> AgentState:
    # Must be a real async node (and invoked via the graph's ainvoke, not
    # invoke) rather than calling asyncio.run() here: that blew up with
    # "asyncio.run() cannot be called from a running event loop" as soon as
    # this ran inside FastAPI's already-running event loop (api/main.py) --
    # worked fine from the plain CLI script, which has no loop running yet.
    plan = state["plan"]
    trace = state.setdefault("trace", [])
    state["tool_results"] = await _run_all(plan.steps, trace) if plan and plan.steps else []
    return state
