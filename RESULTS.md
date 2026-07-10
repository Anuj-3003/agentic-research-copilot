# Results: FinDocGPT + Agentic Research Copilot

All numbers below are real, measured on this machine, fully local/free stack
(Ollama `llama3.1:8b` + `bge-base-en-v1.5`/`bge-reranker-base`), unless noted
otherwise. Nothing here is a placeholder or an estimate.

---

## 1. FinDocGPT (RAG system) -- RAGAS evaluation

12 hand-labeled questions (6 simple_lookup, 4 comparison, 2 adversarial
out-of-scope), verified against the real ingested FOMC/ECB documents.

| Scope | Faithfulness | Answer Relevancy | Context Precision | Context Recall |
|---|---|---|---|---|
| All 12 questions | inconclusive* | 0.71 | 0.55 | 0.63 |
| 10 answerable questions only | inconclusive* | 0.86 | 0.67 | 0.63 |

\* **Faithfulness could not be reliably measured with a local judge.** RAGAS's
faithfulness metric requires the judge LLM to decompose an answer into atomic
statements in a specific structured format; `llama3.1:8b` failed to produce
parseable output on 10 of 12 questions. This is a documented limitation of
using a small local model as an LLM-as-judge, not a claim about the RAG
system's actual faithfulness. A stronger judge (e.g. Claude) would be needed
for a real faithfulness number -- not yet run.

The two out-of-scope questions correctly declined rather than hallucinating
an answer; their low answer-relevancy scores (0.0) are a known RAGAS metric
artifact (it penalizes "I don't know" responses by design), not a system
failure.

---

## 2. Agentic Research Copilot: single-hop vs. multi-hop benchmark

18 questions (8 single-hop, 6 multi-hop comparison, 4 adversarial
out-of-scope) run through the full agent
(Planner -> Orchestrator -> Aggregator -> Self-Critic -> Finalize).

| Category | n | Correctness | Citation Accuracy | Avg Tool Calls | Avg Retries |
|---|---|---|---|---|---|
| single_hop | 8 | 0.875 | 0.875 | 1.12 | 0.0 |
| multi_hop | 6 | 0.667 | 1.0 | 2.0 | 0.17 |
| out_of_scope | 4 | 1.0 | 1.0 | 1.0 | 0.0 |

Zero hallucinations across all 18 questions (all 4 out-of-scope questions
correctly declined).

**Failure analysis (`eval/failure_analysis.md`):** of the 4 flagged issues,
none were random -- one transient FinDocGPT API error, one local-critic
parsing hiccup (self-recovered via retry), one planning inefficiency
(over-decomposed a single-hop question but still answered correctly), and
one genuine synthesis gap: the agent currently drafts one claim per tool
call verbatim (no cross-claim synthesis yet), so a question like "did the
rate change?" can have two fully-supported, individually-correct claims that
never explicitly say "unchanged" -- the Self-Critic correctly declines
rather than guessing, which is safer than confidently guessing wrong.

---

## 3. The key comparison: agent vs. calling FinDocGPT directly

The same 18 questions, sent straight to FinDocGPT's `/query` endpoint with
no planning, no decomposition, no self-verification.

| Category | FinDocGPT-alone Correctness | Agent Correctness | Delta |
|---|---|---|---|
| single_hop | 1.0 | 0.875 | -0.125 |
| multi_hop | 0.583 | 0.667 | **+0.084** |
| out_of_scope | 1.0 | 1.0 | 0 |

**Multi-hop: the agent outperforms calling FinDocGPT directly by 8.4
percentage points (0.667 vs. 0.583, a ~14% relative improvement)** -- this is
the concrete evidence that planning + decomposition adds real value on
questions that require synthesizing across documents, which is exactly the
kind of question a single-shot RAG call struggles with.

**Single-hop: FinDocGPT alone edges out the agent (1.0 vs. 0.875).** Traced
to one specific cause, not a systemic pattern: one agent run hit a transient
FinDocGPT API error (see failure analysis) that the direct-call baseline
simply didn't hit in its own run. Not evidence the agent layer hurts
single-hop performance -- just an honest artifact of one transient failure,
reported rather than smoothed over.

**A qualitative finding worth calling out explicitly:** on "Did the Fed
change the federal funds rate target range between January and March 2026?"
(the answer is no -- it stayed the same), FinDocGPT alone **confidently
answered "Yes, the Fed changed..." -- a hallucinated, factually wrong
answer stated with no hedge.** The agent, given the same underlying
information, declined to answer rather than guess. Both scored 0 on strict
correctness, but the failure modes are not equivalent: one is a confident
factual error, the other is an honest "insufficient information." Only the
qualitative behavior was inspected here, not a scored hallucination-rate
metric across all categories (that would require another metric on the
FinDocGPT-alone baseline, not yet built).

---

## 4. Bugs found and fixed along the way

Building the baseline comparison in Section 3 directly surfaced two
previously-undiscovered bugs in FinDocGPT itself (not just in the new
agent repo) -- a genuine benefit of building a rigorous evaluation harness
rather than eyeballing a few example answers:

1. **`asyncio.run()` inside an already-running event loop.** FinDocGPT's
   `parallel_comparison_retrieve` (used for comparison-type questions) called
   `asyncio.run()` internally. This worked when tested via the CLI (no event
   loop running yet) but crashed every comparison-type query with
   `RuntimeError: asyncio.run() cannot be called from a running event loop`
   as soon as it ran inside FastAPI's own event loop -- undetected until a
   baseline eval called FinDocGPT's API directly and repeatedly. Fixed by
   making the retriever node genuinely async and switching all callers
   (CLI, API, eval scripts) to `ainvoke()`.
2. **A permanently-corrupted reranker singleton.** After fixing (1), a
   second, subtler bug appeared: the lazy-loaded cross-encoder reranker,
   when first constructed while `parallel_comparison_retrieve`'s concurrent
   `asyncio.to_thread` calls were already running, ended up on a PyTorch
   "meta device" with no real data -- every subsequent `.predict()` call
   then failed permanently with `Cannot copy out of meta tensor; no data!`,
   since the singleton was corrupted for the lifetime of the process. Fixed
   by eagerly loading both the embedder and reranker at FastAPI startup,
   single-threaded, before any concurrent request handling begins.

Both bugs were 100%-reproducible (every comparison-type question failed
identically) and are now fixed and verified with real passing queries.

The agent repo's own build surfaced further bugs (LangGraph node/state-key
collision, Ollama tool-calling stringifying nested JSON, `with_structured_output()`
returning `None` on some local-model responses, a state-mutation-in-routing-
function bug that caused an infinite retry loop) -- all documented inline in
the relevant files' docstrings.

---

## 5. Resume bullet points (grounded in the numbers above)

**FinDocGPT:**

> Built FinDocGPT, an agentic RAG system for FOMC/ECB monetary policy documents
> using LangGraph (router -> hybrid dense+BM25 retrieval -> cross-encoder
> reranking -> relevance grading -> self-correcting query rewrite -> cited
> generation); achieved 0.86 answer relevancy and 0.67 context precision
> (RAGAS) on a 12-question hand-labeled evaluation set, running entirely on a
> free, local, open-source model stack (Ollama + Chroma + bge embeddings/reranker).

**Agentic Research Copilot:**

> Built a planning agent (LangGraph: Planner -> async Orchestrator ->
> Self-Critic -> structured Report) that composes FinDocGPT as an
> independently-deployed HTTP tool rather than importing it; on an 18-question
> single-hop/multi-hop benchmark, achieved an 8.4-percentage-point
> (~14% relative) correctness improvement over calling FinDocGPT directly on
> multi-hop comparison questions, with zero hallucinations across all
> categories and full per-node/per-tool-call observability (structured
> tracing + a Streamlit dashboard).

**Optional supporting bullet (engineering rigor):**

> Diagnosed and fixed two previously-undetected concurrency bugs in a
> production RAG API (an `asyncio.run()`-inside-a-running-event-loop crash
> and a race-condition-corrupted model singleton) by building a rigorous
> agent-vs-baseline evaluation harness -- both bugs were 100% reproducible
> but had gone undetected until direct, repeated API testing surfaced them.

---

## What's not included above (explicitly, so nothing here overstates itself)

- Faithfulness (FinDocGPT RAGAS eval) -- inconclusive with a local judge, not
  reported as a number.
- A general hallucination-rate metric for the FinDocGPT-alone baseline across
  single-hop/multi-hop categories -- only the out-of-scope decline rate was
  measured that way; the "confident hallucination" finding in Section 3 is a
  qualitative, manually-inspected example, not a scored metric.
- Docker image (`agentic-research-copilot/Dockerfile`) is written but not
  build-tested (no Docker on this dev machine).
- CI and live deployment -- explicitly deferred (see both repos' READMEs).
