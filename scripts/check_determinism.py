import json
from src.task2_account_brief.pipeline import generate_account_brief

run1 = generate_account_brief(company="Omni Consumer Products", window_days=None)
run2 = generate_account_brief(company="Omni Consumer Products", window_days=None)

d1 = run1.model_dump(mode="json")
d2 = run2.model_dump(mode="json")

if d1 == d2:
    print("✓ IDENTICAL - full determinism confirmed")
else:
    print("✗ NOT IDENTICAL - diffing fields:")
    for key in d1:
        if d1[key] != d2[key]:
            print(f"\n--- {key} (run 1) ---")
            print(json.dumps(d1[key], indent=2))
            print(f"--- {key} (run 2) ---")
            print(json.dumps(d2[key], indent=2))
