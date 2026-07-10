"""
agent/graph.py
Planner -> Orchestrator -> Aggregator -> Self-Critic -> conditional:
  PASS / INSUFFICIENT_INFO   -> Finalize -> END
  RETRY (under MAX_RETRIES)  -> back to Planner (with critic feedback)
  RETRY (retries exhausted)  -> Finalize as INSUFFICIENT_INFO -> END
"""
import asyncio

from langgraph.graph import StateGraph, END

from agent.schemas import AgentState
from agent.planner import planner_node
from agent.orchestrator import orchestrator_node
from agent.aggregator import aggregator_node
from agent.self_critic import self_critic_node
from agent.finalize import finalize_node
from agent.tracing import save_trace


def route_after_critic(state: AgentState) -> str:
    # Read-only: self_critic_node already downgrades RETRY to
    # INSUFFICIENT_INFO once retries are exhausted, so this just reacts to
    # whatever verdict is already committed in state.
    return "retry" if state["critic_result"].verdict == "RETRY" else "finalize"


def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("planner", planner_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("aggregator", aggregator_node)
    workflow.add_node("self_critic", self_critic_node)
    workflow.add_node("finalize", finalize_node)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "orchestrator")
    workflow.add_edge("orchestrator", "aggregator")
    workflow.add_edge("aggregator", "self_critic")
    workflow.add_conditional_edges(
        "self_critic", route_after_critic, {"retry": "planner", "finalize": "finalize"}
    )
    workflow.add_edge("finalize", END)

    return workflow.compile()


app = build_graph()


async def arun(question: str) -> dict:
    # The graph has an async node (orchestrator), so it must run via
    # ainvoke -- LangGraph's sync invoke() raises TypeError on an async-only
    # node ("No synchronous function provided"). Callers already inside an
    # event loop (api/main.py) should await arun()/app.ainvoke() directly
    # instead of going through the sync run() wrapper below.
    result = await app.ainvoke({
        "question": question,
        "plan": None,
        "tool_results": [],
        "draft_report": None,
        "critic_result": None,
        "retry_count": 0,
        "final_output": "",
        "trace": [],
    })
    trace_path = save_trace(result)
    print(f"Trace saved to {trace_path}")
    return result


def run(question: str) -> dict:
    return asyncio.run(arun(question))


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "What was the federal funds rate target range set at the January 2026 FOMC meeting?"
    result = run(q)
    print("Plan:", result["plan"])
    print()
    print("Critic verdict:", result["critic_result"].verdict, "-", result["critic_result"].reason)
    print()
    print("Final output:\n" + result["final_output"])
