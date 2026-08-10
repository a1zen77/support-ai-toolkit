# Eval Report

Generated: 2026-08-10T11:57:18.589301+00:00

**Overall: 6/6 passed, mean score 1.00**

## task1_triage

6/6 passed, mean score 1.00

| Case ID | Adversarial | Passed | Score | Description | Reasoning |
|---|---|---|---|---|---|
| task1_clear_p1_urgency |  | ✓ | 1.00 | Unambiguous production outage should classify as P1 | Correctly classified as P1 |
| task1_adversarial_billing_no_product_signal | ⚠️ | ✓ | 1.00 | ADVERSARIAL: billing question with zero product-name signal - regression guard for classify_v3/v4 fixes | Correctly categorized, routed, and product_area is a real technical area (not 'Billing') |
| task1_kb_exact_error_code_match |  | ✓ | 1.00 | A ticket citing a known error code should surface an exact-match KB doc | Found exact KB match: troubleshooting/performance-and-integrations.md |
| task1_product_area_never_blank |  | ✓ | 1.00 | Regression guard: product_area must never be blank (classify_v2 fix) | product_area is non-blank and schema-valid |
| task1_draft_response_quality_judge |  | ✓ | 1.00 | LLM-judge: draft response is professional and doesn't fabricate unsupported specifics | [judge: YES] Stays professional, avoids promising a fix timeline, and does not invent technical details. |
| task1_adversarial_empty_body | ⚠️ | ✓ | 1.00 | ADVERSARIAL: near-empty ticket (subject='help', body='') should not crash or fabricate specifics | Handled empty/near-empty input without crashing and appropriately asked for more detail |
