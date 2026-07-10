"""
eval/failure_analysis.py
Phase 7: categorizes failed benchmark cases by type and writes a markdown
report -- a categorized breakdown is more useful than a single pass/fail
number for deciding what to actually fix next.

Usage:
    python -m eval.failure_analysis
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def categorize(row: dict) -> list[str]:
    types = []
    if row["hallucinated"]:
        types.append("hallucination")
    if row["tool_errors"] > 0:
        types.append("tool_error")
    if row["citation_accuracy"] < 1.0:
        types.append("citation_error")
    if row["category"] != "out_of_scope" and row["correctness"] < 1.0:
        types.append("incorrect_or_incomplete_answer")
    if row["category"] == "multi_hop" and row["num_tool_calls"] < row["min_tool_calls"]:
        types.append("planning_error_underdecomposed")
    if row["category"] == "single_hop" and row["num_tool_calls"] > row["min_tool_calls"]:
        types.append("planning_inefficiency_overdecomposed")
    if row["critic_verdict"] == "INSUFFICIENT_INFO" and row["category"] != "out_of_scope":
        types.append("critic_forced_decline")
    return types


def run(results_path: str = "eval/benchmark_results.json", out_path: str = "eval/failure_analysis.md"):
    with open(results_path) as f:
        data = json.load(f)

    rows = data["per_question"]
    failures = []
    for row in rows:
        types = categorize(row)
        if types:
            failures.append({**row, "failure_types": types})

    by_type: dict[str, list[dict]] = {}
    for f in failures:
        for t in f["failure_types"]:
            by_type.setdefault(t, []).append(f)

    lines = [
        "# Failure Analysis",
        "",
        f"{len(failures)} of {len(rows)} benchmark questions had at least one flagged issue.",
        "",
    ]
    if not by_type:
        lines.append("No failures found.")
    for failure_type, items in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"## {failure_type} ({len(items)})")
        lines.append("")
        for item in items:
            lines.append(f"- **[{item['category']}]** {item['question']}")
            lines.append(f"  - correctness={item['correctness']}, citation_accuracy={item['citation_accuracy']}, "
                          f"tool_calls={item['num_tool_calls']}/{item['min_tool_calls']}, "
                          f"retries={item['retry_count']}, verdict={item['critic_verdict']}")
            lines.append(f"  - final_output: {item['final_output'][:200]}")
        lines.append("")

    report = "\n".join(lines)
    with open(out_path, "w") as f:
        f.write(report)
    print(report)
    return out_path


if __name__ == "__main__":
    run()
