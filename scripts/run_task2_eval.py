from pathlib import Path
from eval.harness_core import run_all, write_report
from eval.task2_cases import get_task2_cases

report = run_all(get_task2_cases())
json_path, md_path = write_report(report, Path("eval"))
print(f"\nWrote {json_path} and {md_path}")
