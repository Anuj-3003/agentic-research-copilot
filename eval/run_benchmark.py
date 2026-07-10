"""
eval/run_benchmark.py
Phase 7: runs the single-hop vs. multi-hop benchmark end-to-end and scores
correctness, citation accuracy, tool-use, and hallucination rate -- reported
separately per category, since that contrast is the concrete evidence the
planning/orchestration layer adds value over calling FinDocGPT directly.

Saves per-question results incrementally (same lesson learned the hard way
running FinDocGPT's RAGAS eval on this machine: long local-LLM eval runs get
interrupted by Windows Update, and losing all progress each time is not
acceptable) -- re-running this script resumes from eval/benchmark_results.json
instead of starting over.

Usage:
    python -m eval.run_benchmark
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.graph import arun
from eval.scoring import score_correctness
import asyncio


def score_question(item: dict, result: dict) -> dict:
    final_output = result["final_output"]
    critic = result["critic_result"]
    report = result["draft_report"]
    tool_results = result["tool_results"]
    category = item["category"]

    correctness, hallucinated = score_correctness(category, item.get("expected_facts", []), final_output)

    # Citation accuracy: every claim's source_ref must trace back to a real,
    # non-errored tool call -- catches the aggregator/finalize inventing a
    # citation FinDocGPT never actually returned.
    valid_refs = {r.step.tool_input for r in tool_results if not r.error}
    claims = report.claims if report else []
    if claims:
        citation_accuracy = sum(1 for c in claims if c.source_ref in valid_refs) / len(claims)
    else:
        citation_accuracy = 1.0 if category == "out_of_scope" else 0.0

    return {
        "question": item["question"],
        "category": category,
        "correctness": round(correctness, 3),
        "citation_accuracy": round(citation_accuracy, 3),
        "num_tool_calls": len(tool_results),
        "min_tool_calls": item.get("min_tool_calls", 1),
        "tool_errors": sum(1 for r in tool_results if r.error),
        "retry_count": result["retry_count"],
        "critic_verdict": critic.verdict if critic else None,
        "hallucinated": hallucinated,
        "final_output": final_output,
    }


def summarize(results: list[dict]) -> dict:
    by_cat: dict[str, list[dict]] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)

    summary = {}
    for cat, rows in by_cat.items():
        summary[cat] = {
            "n": len(rows),
            "avg_correctness": round(sum(x["correctness"] for x in rows) / len(rows), 3),
            "avg_citation_accuracy": round(sum(x["citation_accuracy"] for x in rows) / len(rows), 3),
            "avg_tool_calls": round(sum(x["num_tool_calls"] for x in rows) / len(rows), 2),
            "avg_retry_count": round(sum(x["retry_count"] for x in rows) / len(rows), 2),
            "hallucination_rate": round(sum(1 for x in rows if x["hallucinated"]) / len(rows), 3),
        }
    return summary


def run_benchmark(benchmark_path: str = "eval/benchmark.json", out_path: str = "eval/benchmark_results.json"):
    with open(benchmark_path) as f:
        benchmark = json.load(f)

    results = []
    if os.path.exists(out_path):
        with open(out_path) as f:
            results = json.load(f).get("per_question", [])
    already_scored = {r["question"] for r in results}

    for i, item in enumerate(benchmark):
        if item["question"] in already_scored:
            print(f"[{i + 1}/{len(benchmark)}] already scored, skipping: {item['question']}")
            continue
        print(f"[{i + 1}/{len(benchmark)}] {item['category']}: {item['question']}")

        # arun() (not the raw graph) since the orchestrator node is async --
        # LangGraph requires ainvoke for any graph with an async node. arun()
        # also saves the trace itself, so no separate save_trace() call here.
        state = asyncio.run(arun(item["question"]))
        results.append(score_question(item, state))

        with open(out_path, "w") as f:
            json.dump({"summary": summarize(results), "per_question": results}, f, indent=2)

    summary = summarize(results)
    with open(out_path, "w") as f:
        json.dump({"summary": summary, "per_question": results}, f, indent=2)

    print("\nSummary by category:")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    run_benchmark()
