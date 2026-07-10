# Agentic Research Copilot

**Status: Planner, Orchestrator, Self-Critic, structured Report,
observability, an HTTP API, and an evaluation harness are all built and
verified end-to-end.** Docker image is written but not build-tested locally
(no Docker on this dev machine). Live deployment and CI are not set up yet --
see `guide.md` in the FinDocGPT repo for the full phased plan.

A planning-and-tool-use agent that decomposes multi-step financial research
questions and orchestrates [FinDocGPT](../findocgpt) -- a hybrid-search RAG
system -- as a composed tool, called over HTTP rather than imported as code,
with self-verification against retrieved sources before it hands back an
answer.

## Why a separate repo

FinDocGPT is a complete, independently-evaluated RAG system. This project
treats it as a proven component and adds the planning, orchestration, and
self-correction/evaluation layer needed to answer questions that require more
than single-shot retrieval, while keeping each system independently demoable
and testable.

## Architecture

```
Question
  -> Planner (LLM, structured ExecutionPlan; multi-hop questions get split
     into independent sub-questions, one FinDocGPT call each)
  -> Orchestrator (async node; asyncio.gather over planned tool calls,
     concurrent)
       -> FinDocGPT tool (HTTP call to FINDOCGPT_API_URL)
  -> Aggregator (assembles a structured Report: one Claim per tool result,
     each citing its source_tool + source_ref)
  -> Self-Critic (verifies every claim is actually supported by its cited
     tool output; PASS / RETRY / INSUFFICIENT_INFO)
       -> RETRY loops back to Planner with the critic's feedback (capped at
          MAX_RETRIES)
       -> PASS / INSUFFICIENT_INFO (or retries exhausted) -> Finalize
  -> Finalize (renders the verified claims, or a graceful decline)
```

Every node and every individual tool call is traced (timestamp, input/output
summary, latency, cost) to `traces/run-*.json`, visualized by
`dashboard.py` (Streamlit). The whole graph is served over HTTP by
`api/main.py` (`POST /query`), in addition to the `agent.graph` CLI.

## Evaluation: single-hop vs. multi-hop

The concrete evidence that the planning/orchestration layer adds value over
calling FinDocGPT directly: an 18-question benchmark (8 single-hop, 6
multi-hop, 4 adversarial out-of-scope), scored on correctness, citation
accuracy, tool-use, and hallucination rate.

| Category | n | Correctness | Citation Accuracy | Avg Tool Calls | Hallucination Rate |
|---|---|---|---|---|---|
| single_hop | 8 | 0.875 | 0.875 | 1.12 | 0.0 |
| multi_hop | 6 | 0.667 | 1.0 | 2.0 | 0.0 |
| out_of_scope | 4 | 1.0 | 1.0 | 1.0 | 0.0 |

Multi-hop correctness trails single-hop, and it's traceable to one specific,
honest gap rather than random failure: claims are still 1:1 with individual
tool answers (no Synthesizer step yet), so a question like "did the rate
change between January and March?" can have two fully-supported claims that
each independently restate the same rate, without anything ever explicitly
saying "unchanged" -- the Self-Critic correctly declines rather than
guessing. Full breakdown and categorized failures in
`eval/failure_analysis.md`.

```bash
python -m eval.run_benchmark       # re-run (resumes from eval/benchmark_results.json)
python -m eval.failure_analysis    # regenerate the categorized write-up
```

## Setup

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt   # Windows
cp .env.example .env   # defaults point at a local FinDocGPT dev server
```

FinDocGPT's own API must be running (`uvicorn api.main:app` from the
FinDocGPT repo) for the tool call to succeed -- this repo does not
re-implement retrieval.

## Run

```bash
python -m agent.graph "What was the federal funds rate target range set at the January 2026 FOMC meeting?"
uvicorn api.main:app --port 8001    # serve over HTTP instead
streamlit run dashboard.py          # visualize the trace of any past run
```

## Known limitation: local LLM as judge

The Self-Critic (and Planner) run on `llama3.1:8b` by default. A local 8B
model initially produced a false positive here -- rejecting a claim that was
an almost-verbatim, fully-supported restatement of its source, hallucinating
a discrepancy that didn't exist. Fixed for free via prompting (an
`evidence_check` field forcing the model to quote matching text before
deciding, plus an explicit "paraphrasing isn't embellishment" rule) rather
than switching to a paid judge -- see `agent/self_critic.py`'s docstring for
the full story. `LLM_BACKEND=claude` is available as a drop-in upgrade if
judgment quality becomes a bottleneck again.

## Not built yet (see guide.md Phase 8)

- Live deployment (Docker image exists, not yet pushed/deployed anywhere)
- CI (eval-on-push needs either a hosted Ollama + FinDocGPT reachable from
  the CI runner, or LLM_BACKEND=claude for CI-only judging -- free-tier CI
  runners can't run Ollama, the same constraint FinDocGPT's own README
  already flags for its own deployment)
- Additional tools beyond FinDocGPT (calculator/code-exec, etc.)
