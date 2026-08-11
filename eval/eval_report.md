# Eval Report

Generated: 2026-08-11T06:01:59.313441+00:00

**Overall: 7/7 passed, mean score 1.00**

## task2_account_brief

7/7 passed, mean score 1.00

| Case ID | Adversarial | Passed | Score | Description | Reasoning |
|---|---|---|---|---|---|
| task2_verbatim_quotes_end_to_end |  | ✓ | 1.00 | Every RiskFlag.quote in the final brief must be an exact substring of its source | All 1 risk flag quote(s) verified verbatim in source |
| task2_determinism |  | ✓ | 1.00 | Same account input twice must produce byte-identical AccountBrief (temp=0, seed=42) | Two runs on identical input produced byte-identical output |
| task2_talking_points_no_artifacts |  | ✓ | 1.00 | Regression guard: talking_points must be plain sentences, no leading dash/bullet/number | All 2 talking points are clean plain sentences |
| task2_executive_summary_grounded |  | ✓ | 1.00 | Executive summary should reference real account facts, not generic boilerplate | Executive summary references 2/3 checked grounding signals from real account data |
| task2_risk_explanation_adds_value_judge |  | ✓ | 1.00 | LLM-judge: risk explanation interprets the quote rather than just restating it | [judge: YES] The explanation provides meaningful context by inferring potential churn intent, which is crucial for assessing account health. |
| task2_adversarial_zero_signal_account | ⚠️ | ✓ | 1.00 | ADVERSARIAL: account with zero risk candidates must not have fabricated risk flags | Correctly produced zero risk flags for an account with zero real candidates - no fabrication |
| task2_adversarial_unknown_account | ⚠️ | ✓ | 1.00 | ADVERSARIAL: nonexistent company must fail gracefully with a clear ValueError, not crash or silently succeed | Unknown company raises a clear, correctly-typed ValueError with an actionable message |
