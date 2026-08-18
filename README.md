# Support & TAM AI Toolkit

Internal AI tooling for Technical Support and TAM teams, built entirely on
a local stack — no external API calls, no external data beyond the
provided mock dataset (500 tickets, 50 accounts, 9 KB docs).

**Stack:** Ollama (`qwen2.5:7b-instruct`) for generation, sentence-transformers
(`all-MiniLM-L6-v2`) for embeddings, FastAPI for the REST layer, Pydantic v2
for schema validation. No vector DB — plain numpy cosine similarity over a
small (~86 chunk) knowledge base.

## Highlights

- Built a fully local AI pipeline (Ollama + sentence-transformers, zero
  external API calls) handling ticket triage, KB retrieval, and account
  risk summarization across 500 tickets / 50 accounts.
- Designed a structural anti-hallucination guarantee for risk flagging:
  quotes are extracted via non-LLM keyword matching before the LLM ever
  runs, and the LLM's output schema has no field capable of holding quote
  text — fabrication is prevented by the schema, not just by prompting.
- Built a custom eval harness (13 test cases, rule-based + LLM-as-judge,
  adversarial coverage) that caught two real production bugs during
  development — a retry-exhaustion failure and a schema field-confusion
  bug — both fixed and re-verified with before/after evidence.
- Verified deterministic output (temperature=0, fixed seed) end-to-end,
  including through the REST layer, via an automated byte-identical
  diff check across repeated runs.
- Surfaced and worked around a real data-quality issue in the provided
  dataset (unreliable foreign key), documented with the verification
  method used to catch it.

## Setup

```bash
git clone <https://github.com/a1zen77/support-ai-toolkit>
cd support-ai-toolkit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # defaults work as-is, no secrets required

# Requires Ollama running locally with the model pulled:
ollama pull qwen2.5:7b-instruct
```

Start the API:

```bash
uvicorn app.main:app --reload
```

All commands below assume this venv is active and commands are run from
the project root (some scripts require `PYTHONPATH=.` explicitly — noted
where relevant).

## Task 1 — Triage Agent

Classifies an incoming ticket (product, area, category, urgency), matches
it against the knowledge base, routes it to a responder team, and drafts a
first response.

**Sample run:**

```bash
curl -s -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "SSO login failing for all users",
    "body": "Since this morning none of our users can log in via SSO. We are seeing AUTH_TOKEN_EXPIRED errors. This is blocking our entire team."
  }' | python3 -m json.tool
```

Returns a structured `TriageResult`: product, product_area, category +
reasoning, urgency + reasoning, KB matches with traceable citations,
recommended responder team, and a grounded draft response. A `/triage/raw`
endpoint also accepts unstructured free-text input.

## Task 2 — Account Health Summariser

Generates a 3-section brief (executive summary, risks & flags, talking
points) for a given account. Risk flags are justified with verbatim
quotes extracted via non-LLM keyword matching *before* the LLM ever runs
— the LLM selects from and narrates around pre-verified candidates, but
its output schema has no field capable of holding quote text at all, so
it structurally cannot fabricate one.

**Sample run:**

```bash
curl -s -X POST http://localhost:8000/account-brief \
  -H "Content-Type: application/json" \
  -d '{"company": "Omni Consumer Products", "window_days": null}' | python3 -m json.tool
```

Output is deterministic for identical input (`LLM_TEMPERATURE=0`,
`LLM_SEED=42`) — verified by a dedicated eval case that runs the same
account twice and asserts byte-identical output.

## Task 3 — Eval Harness

```bash
PYTHONPATH=. python3 eval/run_eval.py
```

Runs 13 eval cases (6 for Task 1, 7 for Task 2) mixing rule-based and
LLM-as-judge scoring, including two adversarial cases per task. Writes
`eval/eval_report.json` and `eval/eval_report.md`. A separate, faster
pytest suite (`eval/test_risk_signals.py`, `eval/test_pipeline.py`) also
exists for CI-style regression testing of the non-LLM verbatim-quote
guarantee specifically:

```bash
PYTHONPATH=. python3 -m pytest eval/ -m "not slow" -v
```

The eval harness caught two real bugs during development (a
retry-exhaustion failure on zero-product-signal tickets, and a
category/product_area field-confusion bug) — both are documented with
before/after evidence in the design note below.

## Task 4 — Design Note

See [`docs/design_note.md`](docs/design_note.md) for failure modes,
the latency/quality trade-off, data sensitivity, and scaling discussion.

## Notes on design decisions

- Tickets join to accounts on `company`, not `account_id` — verified only
  4/500 tickets have an `account_id` matching `accounts.json` at all, and
  even those are coincidental mismatches.
- `AS_OF_DATE` is fixed to the dataset's max ticket timestamp
  (2026-05-22), not wall-clock time.
- All prompts are versioned with an inline changelog (`prompts.py` in each
  task module) documenting why each revision happened.