from eval.harness_core import run_case
from eval.task1_cases import _case_billing_routes_to_billing_team

result = run_case(_case_billing_routes_to_billing_team())
print(f"passed={result.passed} score={result.score} reasoning={result.reasoning}")
if result.error:
    print(f"error: {result.error}")
