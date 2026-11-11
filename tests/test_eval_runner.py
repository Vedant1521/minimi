"""
Pytest integration for the automated temporal and grounding evaluation suite.
"""

from pathlib import Path
from scripts.eval_temporal import run_temporal_evaluations


def test_temporal_eval_benchmark():
    """Verify that the evaluation suite executes cleanly and exceeds the 90% accuracy threshold."""
    dataset_path = Path(__file__).parent / "data" / "eval_temporal_cases.json"
    assert dataset_path.exists(), f"Evaluation dataset missing at {dataset_path}"

    results = run_temporal_evaluations(dataset_path)
    assert len(results) >= 15, "Expected at least 15 evaluation cases in dataset"

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    pass_rate = (passed / total) * 100

    # Ensure 100% pass rate on curated benchmark
    failed_details = [f"{r.case_id} ({r.category}): {r.details}" for r in results if not r.passed]
    assert pass_rate >= 90.0, f"Pass rate {pass_rate:.1f}% below 90%. Failures: {failed_details}"
    assert passed == total, f"Expected all cases to pass. Failures: {failed_details}"
