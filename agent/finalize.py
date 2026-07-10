"""
agent/finalize.py
Renders the (verified) draft Report into the final human-readable output,
once the Self-Critic reaches a terminal verdict (PASS or INSUFFICIENT_INFO,
or retries are exhausted).
"""
from agent.schemas import AgentState
from agent.tracing import traced


@traced(
    "finalize",
    describe_input=lambda s: s["critic_result"].verdict if s.get("critic_result") else "n/a",
    describe_output=lambda s: s["final_output"][:200],
)
def finalize_node(state: AgentState) -> AgentState:
    critic = state["critic_result"]
    report = state["draft_report"]

    if critic and critic.verdict == "INSUFFICIENT_INFO":
        state["final_output"] = (
            "I wasn't able to gather enough verified information to answer this "
            f"question confidently. ({critic.reason})"
        )
        return state

    if not report or not report.claims:
        state["final_output"] = "No tool produced a usable, verified result for this question."
        return state

    lines = [f"- {c.text} [source: {c.source_tool}:{c.source_ref}]" for c in report.claims]
    state["final_output"] = "\n".join(lines)
    return state
