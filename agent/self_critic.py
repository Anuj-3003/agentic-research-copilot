"""
agent/self_critic.py
Phase 4: verifies every claim in the draft Report is actually supported by
the tool output it cites, catching the aggregator inventing or embellishing
claims beyond what a tool actually returned. Note: at this stage claims are
still 1:1 with tool answers (Phase 5 aggregator), so this mostly guards
against the LLM paraphrasing a claim into something the source didn't say --
it becomes more load-bearing once a Synthesizer step (combining multiple
tool answers into one narrative) is added on top.

A local llama3.1:8b critic initially produced a false positive here: it
rejected a claim ("Stephen I. Miran voted against this action...") that was
an almost-verbatim restatement of its cited tool output, hallucinating a
discrepancy that didn't exist. Two changes fixed it without needing a paid
judge: (1) an evidence_check field the model fills before the verdict,
forcing it to quote matching text rather than jump straight to a categorical
judgment, and (2) explicit instruction that paraphrasing/subsetting isn't
embellishment. See CriticResult in schemas.py.
"""
from agent.llm import llm
from agent.schemas import AgentState, CriticResult
from agent.tracing import traced
from config import MAX_RETRIES

CRITIC_PROMPT = """You are a fact-checking critic. A research agent answered \
a question by calling tools and drafting claims. Verify that every claim is \
actually supported by its cited tool output.

Original question: {question}

Draft claims and their cited tool outputs:
{claims_block}

For each claim, first quote the exact matching text from its cited tool output \
in evidence_check (or state precisely what's missing) -- then decide.

Only flag a claim as unsupported if it states a SPECIFIC fact, number, name, \
or date that is completely ABSENT from its cited tool output. A claim that \
paraphrases, shortens, or is a strict subset of what the tool output said is \
NOT embellishment -- do not flag those.

Respond with exactly one verdict:
- PASS: every claim is supported (by the rule above) and the claims collectively answer the question.
- RETRY: at least one claim states a specific fact/number/name/date genuinely \
absent from its cited tool output (explain which, and why, in the reason).
- INSUFFICIENT_INFO: the claims are all supported, but don't contain enough \
information to answer the question (e.g. a tool call failed or returned \
nothing relevant)."""


def _format_claims_block(state: AgentState) -> str:
    by_ref = {r.step.tool_input: r for r in state["tool_results"]}
    lines = []
    for c in state["draft_report"].claims:
        source = by_ref.get(c.source_ref)
        source_desc = source.output.answer if source and not source.error else "(tool call failed)"
        lines.append(f"- Claim: {c.text}\n  Cited tool output: {source_desc}")
    return "\n".join(lines) if lines else "(no claims -- no tool call returned a usable answer)"


@traced(
    "self_critic",
    describe_input=lambda s: f"{len(s['draft_report'].claims)} claim(s) to verify",
    describe_output=lambda s: f"{s['critic_result'].verdict}: {s['critic_result'].reason}",
)
def self_critic_node(state: AgentState) -> AgentState:
    prompt = CRITIC_PROMPT.format(
        question=state["question"],
        claims_block=_format_claims_block(state),
    )
    structured_llm = llm.with_structured_output(CriticResult)

    # Small local models occasionally respond without making a tool call at
    # all, which with_structured_output() surfaces as a bare None rather than
    # an exception -- same class of unreliability FinDocGPT's generator_node
    # already works around with a stricter-prompt retry.
    result = structured_llm.invoke(prompt)
    if result is None:
        result = structured_llm.invoke(prompt + "\n\nRespond by calling the tool with all three fields filled in. Do not respond with plain text.")
    if result is None:
        result = CriticResult(
            evidence_check="(critic failed to produce a parseable response twice)",
            verdict="INSUFFICIENT_INFO",
            reason="The fact-checking critic failed to produce a usable verdict.",
        )

    # All retry bookkeeping happens here, in a real node -- LangGraph only
    # persists state changes made by node return values, not by mutations
    # inside a conditional-edge routing function (that caused an infinite
    # loop the first time: retry_count never actually advanced, hitting the
    # recursion limit instead of ever stopping).
    if result.verdict == "RETRY":
        retry_count = state.get("retry_count", 0)
        if retry_count >= MAX_RETRIES:
            result.verdict = "INSUFFICIENT_INFO"
            result.reason = f"Retries exhausted ({MAX_RETRIES}). Last issue: {result.reason}"
        else:
            state["retry_count"] = retry_count + 1

    state["critic_result"] = result
    return state
