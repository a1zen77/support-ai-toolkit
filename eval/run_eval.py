"""
Combined eval harness entry point - runs all Task 1 and Task 2 eval cases
and writes a single eval_report.json / eval_report.md covering both, per
the assignment's Task 3 deliverable requirement.

Usage:
    PYTHONPATH=. python3 eval/run_eval.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from eval.harness_core import run_all, write_report
from eval.task1_cases import get_task1_cases
from eval.task2_cases import get_task2_cases


def main() -> int:
    cases = get_task1_cases() + get_task2_cases()
    print(f"Running {len(cases)} eval cases ({len(get_task1_cases())} Task 1, {len(get_task2_cases())} Task 2)...\n")

    report = run_all(cases)

    out_dir = Path(__file__).resolve().parent
    json_path, md_path = write_report(report, out_dir)

    print(f"\n{'=' * 60}")
    print(f"Overall: {report.total_passed}/{report.total_cases} passed, mean score {report.mean_score:.2f}")
    print(f"Report written to:\n  {json_path}\n  {md_path}")
    print(f"{'=' * 60}")

    # Non-zero exit code on any failure, so this is CI-friendly (relevant
    # for the bonus "automated CI step" item) even though we're running it
    # manually for now.
    return 0 if report.total_passed == report.total_cases else 1


if __name__ == "__main__":
    sys.exit(main())