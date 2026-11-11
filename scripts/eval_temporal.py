"""
Automated evaluation runner for temporal memory, cross-session recall, and evidence grounding.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, List

from rich.console import Console
from rich.table import Table

from minimi.grounding import EvidenceGrounder
from minimi.recall import CrossSessionRecallEngine
from minimi.search import Citation
from minimi.temporal import TemporalParser


@dataclass
class EvalResult:
    """Record of individual test case evaluation."""
    category: str
    case_id: str
    passed: bool
    details: str


def run_temporal_evaluations(dataset_path: Path) -> list[EvalResult]:
    """Execute all evaluation categories against the evaluation dataset."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results: list[EvalResult] = []
    ref_time = datetime(2026, 11, 11, 20, 0, 0, tzinfo=timezone.utc)

    # 1. Temporal Parsing Evaluation
    for case in data.get("temporal_parsing_cases", []):
        window = TemporalParser.parse(case["query"], reference_time=ref_time)
        if case["is_temporal"]:
            passed = window is not None and window.label == case["expected_label"]
            details = f"Got label: '{getattr(window, 'label', None)}' | Expected: '{case['expected_label']}'"
        else:
            passed = window is None
            details = f"Expected None | Got: '{getattr(window, 'label', None)}'"

        results.append(
            EvalResult(
                category="Temporal Parsing",
                case_id=case["id"],
                passed=passed,
                details=details,
            )
        )

    # 2. Cross-Session Recall Intent & Keyword Extraction
    for case in data.get("recall_intent_cases", []):
        is_recall = CrossSessionRecallEngine.is_recall_query(case["query"])
        keywords = CrossSessionRecallEngine.extract_keywords(case["query"])

        if case["is_recall"]:
            expected_kw = set(case["expected_keywords"])
            passed = is_recall and bool(keywords.intersection(expected_kw))
            details = f"Recall={is_recall} | Matched KW: {keywords.intersection(expected_kw)}"
        else:
            passed = not is_recall
            details = f"Recall={is_recall} | Expected False"

        results.append(
            EvalResult(
                category="Recall Intent & Keywords",
                case_id=case["id"],
                passed=passed,
                details=details,
            )
        )

    # 3. Grounding & Citation Validation
    for case in data.get("grounding_cases", []):
        available_cits = [
            Citation(index=i, title=f"Source {i}", url=f"https://source{i}.org", snippet=f"Snippet {i}")
            for i in case["available_indices"]
        ]
        report = EvidenceGrounder.verify_and_format(case["text"], available_cits)
        passed = (
            report.valid_indices == case["expected_valid"]
            and report.hallucinated_indices == case["expected_hallucinated"]
        )
        details = (
            f"Valid: {report.valid_indices} (exp {case['expected_valid']}) | "
            f"Hallucinated: {report.hallucinated_indices} (exp {case['expected_hallucinated']})"
        )

        results.append(
            EvalResult(
                category="Evidence Grounding",
                case_id=case["id"],
                passed=passed,
                details=details,
            )
        )

    return results


def print_evaluation_summary(results: list[EvalResult], console: Console) -> float:
    """Render a structured Rich table summarizing evaluation results."""
    categories = sorted(list({r.category for r in results}))

    table = Table(title="Minimi Temporal & Grounding Evaluation Suite", border_style="cyan")
    table.add_column("Evaluation Category", style="bold white")
    table.add_column("Total Cases", justify="right")
    table.add_column("Passed", justify="right", style="green")
    table.add_column("Failed", justify="right", style="red")
    table.add_column("Pass Rate", justify="right", style="bold yellow")

    total_all = len(results)
    passed_all = sum(1 for r in results if r.passed)

    for cat in categories:
        cat_results = [r for r in results if r.category == cat]
        total = len(cat_results)
        passed = sum(1 for r in cat_results if r.passed)
        failed = total - passed
        rate = (passed / total * 100) if total else 0.0
        table.add_row(cat, str(total), str(passed), str(failed), f"{rate:.1f}%")

    table.add_section()
    overall_rate = (passed_all / total_all * 100) if total_all else 0.0
    table.add_row(
        "[bold]Overall Performance[/bold]",
        str(total_all),
        str(passed_all),
        str(total_all - passed_all),
        f"[bold]{overall_rate:.1f}%[/bold]",
    )

    console.print(table)
    return overall_rate


def main() -> int:
    """Run CLI evaluation."""
    console = Console()
    dataset_path = Path(__file__).parent.parent / "tests" / "data" / "eval_temporal_cases.json"

    if not dataset_path.exists():
        console.print(f"[bold red]Error: Evaluation dataset not found at {dataset_path}[/bold red]")
        return 1

    console.print(f"[dim]Running evaluations against {dataset_path}...[/dim]\n")
    results = run_temporal_evaluations(dataset_path)
    overall_rate = print_evaluation_summary(results, console)

    if overall_rate >= 90.0:
        console.print(f"[bold green]✔ Evaluation Benchmark Passed ({overall_rate:.1f}% >= 90.0%)[/bold green]")
        return 0
    else:
        console.print(f"[bold red]✘ Evaluation Benchmark Failed ({overall_rate:.1f}% < 90.0%)[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
