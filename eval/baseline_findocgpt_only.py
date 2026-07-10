"""
eval/baseline_findocgpt_only.py
The comparison the guide calls the most important result in the project:
does the Planner/Orchestrator/Self-Critic layer actually add value over
calling FinDocGPT directly, single-shot, with no decomposition? Runs the
exact same 18 benchmark questions straight against FinDocGPT's own /query
endpoint (bypassing the agent entirely) and scores them with the identical
fact-matching logic used for the agent's own benchmark, so the two numbers
are a fair apples-to-apples comparison.

Saves incrementally per-question (same reason as run_benchmark.py: long
local-LLM eval runs on this machine have been interrupted by Windows Update).

Usage:
    python -m eval.baseline_findocgpt_only
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.tools.findocgpt_tool import call_findocgpt
from eval.scoring import score_correctness


async def score_question(item: dict) -> dict:
    question = item["question"]
    category = item["category"]
    try:
        response = await call_findocgpt(question)
        final_output = response.answer
        error = None
    except Exception as e:
        final_output = ""
        error = str(e)

    correctness, hallucinated = score_correctness(category, item.get("expected_facts", []), final_output)
    return {
        "question": question,
        "category": category,
        "correctness": round(correctness, 3),
        "hallucinated": hallucinated,
        "error": error,
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
            "hallucination_rate": round(sum(1 for x in rows if x["hallucinated"]) / len(rows), 3),
        }
    return summary


def run_baseline(benchmark_path: str = "eval/benchmark.json", out_path: str = "eval/baseline_results.json"):
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

        results.append(asyncio.run(score_question(item)))
        with open(out_path, "w") as f:
            json.dump({"summary": summarize(results), "per_question": results}, f, indent=2)

    summary = summarize(results)
    with open(out_path, "w") as f:
        json.dump({"summary": summary, "per_question": results}, f, indent=2)

    print("\nFinDocGPT-alone summary by category:")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    run_baseline()
