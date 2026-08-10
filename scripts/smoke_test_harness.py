from pathlib import Path
from eval.harness_core import EvalCase, ScoreResult, run_all, write_report

cases = [
    EvalCase(
        id="fake_pass",
        task="task1_triage",
        description="a case that should pass",
        run=lambda: {"value": 42},
        score=lambda output: ScoreResult(passed=True, score=1.0, reasoning="42 is correct"),
    ),
    EvalCase(
        id="fake_crash",
        task="task1_triage",
        description="a case whose run() deliberately crashes",
        is_adversarial=True,
        run=lambda: 1 / 0,
        score=lambda output: ScoreResult(passed=True, score=1.0, reasoning="unreachable"),
    ),
]

report = run_all(cases)
json_path, md_path = write_report(report, Path("eval"))
print(f"\nWrote {json_path} and {md_path}")
