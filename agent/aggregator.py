"""
agent/aggregator.py
Phase 5: assembles a structured Report from the Orchestrator's raw tool
results. One claim per successful tool call for now -- each claim is
attributed to the specific tool_input that produced it, which is what the
Self-Critic checks it against.
"""
from agent.schemas import AgentState, Claim, Report
from agent.tracing import traced


@traced(
    "aggregator",
    describe_input=lambda s: f"{len(s['tool_results'])} tool result(s)",
    describe_output=lambda s: f"{len(s['draft_report'].claims)} claim(s) drafted",
)
def aggregator_node(state: AgentState) -> AgentState:
    claims = [
        Claim(
            text=r.output.answer,
            source_tool=r.step.tool,
            source_ref=r.step.tool_input,
            confidence=r.output.confidence or "low",
        )
        for r in state["tool_results"]
        if not r.error and r.output.answer
    ]
    state["draft_report"] = Report(question=state["question"], claims=claims)
    return state
