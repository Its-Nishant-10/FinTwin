"""The six measured dimensions — OWNER: Member 6.

Run:  python -m app.evaluation.benchmark
Writes results to data/benchmark_results.json for the README and the report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RESULTS_PATH = Path(__file__).resolve().parents[3] / "data" / "benchmark_results.json"


def eval_numerical_accuracy() -> dict[str, Any]:
    """Tool output vs. hand-verified expected values.

    TODO(member-6): load app/evaluation/datasets/quant_cases.json — each case is
    (profile, metric, expected). Report exact-match rate and max abs error.
    """
    return {"status": "not_implemented", "metric": "exact_match_rate"}


def eval_tool_selection() -> dict[str, Any]:
    """Does the agent pick the right tool for a question?

    TODO(member-6): 30-50 labelled questions -> (question, expected ToolName).
    Report accuracy and a confusion matrix. This is the headline agentic number.
    """
    return {"status": "not_implemented", "metric": "accuracy"}


def eval_document_extraction() -> dict[str, Any]:
    """TODO(member-6): field-level precision / recall / F1 over labelled statements."""
    return {"status": "not_implemented", "metric": "f1"}


def eval_retrieval_citations() -> dict[str, Any]:
    """TODO(member-6): does the cited source actually support the claim? Report support rate."""
    return {"status": "not_implemented", "metric": "citation_support_rate"}


def eval_simulation_reproducibility() -> dict[str, Any]:
    """Same seed + same inputs must give bit-identical results.

    TODO(member-6): run each scenario twice at seed=42 and assert equality.
    Cheap to implement — do this one first, it protects everyone else.
    """
    return {"status": "not_implemented", "metric": "reproducible_fraction"}


def eval_latency() -> dict[str, Any]:
    """TODO(member-6): end-to-end /agent/ask latency. Report p50 and p95, not the mean."""
    return {"status": "not_implemented", "metric": "p50_p95_ms"}


def run_all() -> dict[str, Any]:
    results = {
        "numerical_accuracy": eval_numerical_accuracy(),
        "tool_selection": eval_tool_selection(),
        "document_extraction": eval_document_extraction(),
        "retrieval_citations": eval_retrieval_citations(),
        "simulation_reproducibility": eval_simulation_reproducibility(),
        "latency": eval_latency(),
        # TODO(member-6): keep a written list of failure cases and model limits.
        "failure_cases": [],
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    print(json.dumps(run_all(), indent=2))
