"""
Core eval harness framework: EvalCase definitions, scoring types, the
runner, and report generation (JSON + Markdown). Test cases for Task 1 and
Task 2 are defined separately (task1_cases.py, task2_cases.py) using this
framework - this file has no knowledge of triage/account-brief specifics.
"""

from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


@dataclass
class ScoreResult:
    passed: bool
    score: float  # 0.0-1.0
    reasoning: str

    def __post_init__(self):
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(f"score must be in [0.0, 1.0], got {self.score}")


@dataclass
class EvalCase:
    id: str
    task: str  # "task1_triage" | "task2_account_brief"
    description: str
    run: Callable[[], Any]              # produces the raw output under test
    score: Callable[[Any], ScoreResult]  # scores that output
    is_adversarial: bool = False


@dataclass
class CaseResult:
    case_id: str
    task: str
    description: str
    is_adversarial: bool
    passed: bool
    score: float
    reasoning: str
    duration_seconds: float
    error: str | None = None  # populated if run() itself raised


@dataclass
class EvalReport:
    generated_at: str
    results: list[CaseResult] = field(default_factory=list)

    @property
    def total_cases(self) -> int:
        return len(self.results)

    @property
    def total_passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def mean_score(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / len(self.results)

    def results_for_task(self, task: str) -> list[CaseResult]:
        return [r for r in self.results if r.task == task]

    def to_dict(self) -> dict:
        by_task: dict[str, dict] = {}
        for task in sorted({r.task for r in self.results}):
            task_results = self.results_for_task(task)
            by_task[task] = {
                "total_cases": len(task_results),
                "passed": sum(1 for r in task_results if r.passed),
                "mean_score": (
                    sum(r.score for r in task_results) / len(task_results)
                    if task_results else 0.0
                ),
                "cases": [
                    {
                        "id": r.case_id,
                        "description": r.description,
                        "is_adversarial": r.is_adversarial,
                        "passed": r.passed,
                        "score": round(r.score, 3),
                        "reasoning": r.reasoning,
                        "duration_seconds": round(r.duration_seconds, 2),
                        "error": r.error,
                    }
                    for r in task_results
                ],
            }

        return {
            "generated_at": self.generated_at,
            "summary": {
                "total_cases": self.total_cases,
                "total_passed": self.total_passed,
                "mean_score": round(self.mean_score, 3),
            },
            "by_task": by_task,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Eval Report",
            "",
            f"Generated: {self.generated_at}",
            "",
            f"**Overall: {self.total_passed}/{self.total_cases} passed, "
            f"mean score {self.mean_score:.2f}**",
            "",
        ]

        for task in sorted({r.task for r in self.results}):
            task_results = self.results_for_task(task)
            task_passed = sum(1 for r in task_results if r.passed)
            task_mean = sum(r.score for r in task_results) / len(task_results)

            lines.append(f"## {task}")
            lines.append("")
            lines.append(f"{task_passed}/{len(task_results)} passed, mean score {task_mean:.2f}")
            lines.append("")
            lines.append("| Case ID | Adversarial | Passed | Score | Description | Reasoning |")
            lines.append("|---|---|---|---|---|---|")
            for r in task_results:
                status = "✓" if r.passed else "✗"
                adv = "⚠️" if r.is_adversarial else ""
                reasoning = r.reasoning.replace("\n", " ")[:200]
                if r.error:
                    first_line = r.error.splitlines()[0] if r.error else ""
                    reasoning = f"CRASHED: {first_line[:150]}"
                lines.append(
                    f"| {r.case_id} | {adv} | {status} | {r.score:.2f} | "
                    f"{r.description} | {reasoning} |"
                )
            lines.append("")

        return "\n".join(lines)


def run_case(case: EvalCase) -> CaseResult:
    start = time.monotonic()
    try:
        output = case.run()
    except Exception as e:
        duration = time.monotonic() - start
        return CaseResult(
            case_id=case.id,
            task=case.task,
            description=case.description,
            is_adversarial=case.is_adversarial,
            passed=False,
            score=0.0,
            reasoning=f"run() raised an exception before scoring could occur.",
            duration_seconds=duration,
            error=f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}",
        )

    try:
        result = case.score(output)
    except Exception as e:
        duration = time.monotonic() - start
        return CaseResult(
            case_id=case.id,
            task=case.task,
            description=case.description,
            is_adversarial=case.is_adversarial,
            passed=False,
            score=0.0,
            reasoning="score() raised an exception - scorer bug, not necessarily a real failure.",
            duration_seconds=duration,
            error=f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}",
        )

    duration = time.monotonic() - start
    return CaseResult(
        case_id=case.id,
        task=case.task,
        description=case.description,
        is_adversarial=case.is_adversarial,
        passed=result.passed,
        score=result.score,
        reasoning=result.reasoning,
        duration_seconds=duration,
        error=None,
    )


def run_all(cases: list[EvalCase], verbose: bool = True) -> EvalReport:
    report = EvalReport(generated_at=datetime.now(timezone.utc).isoformat())
    for case in cases:
        if verbose:
            print(f"Running {case.id} ({case.task})...", end=" ", flush=True)
        result = run_case(case)
        report.results.append(result)
        if verbose:
            status = "PASS" if result.passed else "FAIL"
            print(f"{status} (score={result.score:.2f}, {result.duration_seconds:.1f}s)")
            if result.error:
                print(f"    error: {result.error.splitlines()[0]}")
    return report


def write_report(report: EvalReport, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "eval_report.json"
    md_path = out_dir / "eval_report.md"

    json_path.write_text(json.dumps(report.to_dict(), indent=2))
    md_path.write_text(report.to_markdown())

    return json_path, md_path