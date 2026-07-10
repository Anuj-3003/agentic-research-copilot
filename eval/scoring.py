"""
eval/scoring.py
Shared fact-matching/decline-detection logic used by both the agent
benchmark (run_benchmark.py) and the FinDocGPT-alone baseline
(baseline_findocgpt_only.py) -- kept in one place so the two scorers can't
drift apart, which would make the comparison between them unfair.
"""

DECLINE_MARKERS = [
    "no mention", "not available", "could not be determined", "insufficient",
    "wasn't able", "don't have", "does not contain", "no information",
    "not mentioned", "doesn't contain", "unable to",
]


def fact_group_matched(group: list[str], text: str) -> bool:
    text_l = text.lower()
    return any(alt.lower() in text_l for alt in group)


def score_correctness(category: str, expected_facts: list, final_output: str) -> tuple[float, bool]:
    """Returns (correctness, hallucinated)."""
    if category == "out_of_scope":
        declined = any(m in final_output.lower() for m in DECLINE_MARKERS)
        return (1.0 if declined else 0.0), (not declined)

    matched = sum(1 for g in expected_facts if fact_group_matched(g, final_output))
    correctness = matched / len(expected_facts) if expected_facts else 1.0
    return correctness, False
