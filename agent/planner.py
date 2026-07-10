"""
agent/planner.py
Planner node: decomposes a research question into an ExecutionPlan of tool
calls. Only the "findocgpt" tool exists so far (Phase 3 adds more).
"""
from agent.llm import llm
from agent.schemas import AgentState, ExecutionPlan
from agent.tracing import traced

PLANNER_PROMPT = """You are a research planning agent. Given a financial research \
question, decide what tool calls are needed to answer it.

Available tools:
- findocgpt: a RAG system over FOMC/ECB monetary policy documents (FOMC/ECB \
statements). Use it for any question about central bank policy, interest \
rates, inflation projections, or statement language -- one call per distinct \
sub-question if the question requires comparing multiple things.

Question: {question}

Return a plan as a list of steps. For a simple single-fact question, one step \
is enough. For a question requiring comparison across documents or dates, \
break it into multiple findocgpt steps (one per sub-question), since \
FinDocGPT itself only answers one question per call.{retry_note}"""


@traced(
    "planner",
    describe_input=lambda s: s["question"],
    describe_output=lambda s: f"{len(s['plan'].steps)} step(s): " + "; ".join(
        step.tool_input for step in s["plan"].steps
    ),
)
def planner_node(state: AgentState) -> AgentState:
    retry_note = ""
    critic = state.get("critic_result")
    if critic and critic.verdict == "RETRY":
        retry_note = (
            f"\n\nA previous attempt was rejected by fact-checking: {critic.reason} "
            "Revise the plan to address this -- e.g. rephrase a sub-question to be "
            "more specific, or split it further."
        )

    structured_llm = llm.with_structured_output(ExecutionPlan)
    plan = structured_llm.invoke(
        PLANNER_PROMPT.format(question=state["question"], retry_note=retry_note)
    )
    state["plan"] = plan
    return state
