# Support & TAM AI Toolkit

Internal tooling for Technical Support and Technical Account Management, built entirely
on the provided mock dataset (500 tickets, 50 accounts, 9 knowledge-base docs) with a
**local LLM via Ollama** — no external API calls, no data leaves the machine.

> Status: repo scaffolded, data + KB in place. Tasks 1-4 in progress — this README will
> fill in as each part lands. See "Build Plan" below for what's done vs. pending.

---

## Repo layout

```
support-ai-toolkit/
├── data/                    # provided dataset (tickets.json, accounts.json)
├── knowledge_base/          # provided KB docs (products, troubleshooting, billing, onboarding)
├── src/
│   ├── common/              # shared: Ollama client, config, data loaders
│   ├── kb_retrieval/        # KB indexing + retrieval (Task 1)
│   ├── task1_triage/        # ticket triage pipeline
│   └── task2_account_brief/ # TAM account health summariser
├── app/                     # FastAPI app exposing Task 1 as a REST endpoint
├── ui/                      # bonus: thin Streamlit demo
├── eval/                    # Task 3 eval harness + test cases + reports
├── docs/                    # Task 4 design note
├── tests/                   # unit tests
├── .env.example
└── requirements.txt
```

---

## Setup

**Prerequisites:** Python 3.10+, [Ollama](https://ollama.com) installed locally, ~16GB RAM.

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Pull the local model(s) via Ollama
ollama pull qwen2.5:7b-instruct
# lighter/faster alternative if RAM or speed is tight:
# ollama pull llama3.2:3b

# 4. Start the Ollama server (separate terminal, or as a background service)
ollama serve

# 5. Copy the env template and adjust if needed (defaults work out of the box)
cp .env.example .env
```

Sample runs for each task will be added here as they're implemented.

---

## Build plan

This is the working order — each task builds on the previous one (Task 3 evaluates
Tasks 1 & 2; Task 4 is written from what actually happens in 1-3).

### Setup — done
- [x] Repo scaffold, `.env.example`, `requirements.txt`
- [x] Data + KB confirmed and placed in `data/` and `knowledge_base/`
- [x] Design decisions locked: join tickets↔accounts on `company` (not `account_id`,
      which is unreliable in this dataset — see Design Note); local Ollama LLM;
      configurable `AS_OF_DATE` for "last 90 days" windows

### Task 1 — Ticket Triage Agent
1. `src/common/` — config loader (reads `.env`), Ollama client wrapper (sync call +
   JSON-mode + retry-on-invalid-schema), Pydantic models for ticket input/output.
2. `src/kb_retrieval/` — build a local embedding index (sentence-transformers) over
   the 9 KB docs, chunked by section/heading. Add exact-match lookup for the error
   codes and symptom phrases the KB docs already define (e.g. `AUTH_TOKEN_EXPIRED`,
   `RATE_LIMIT_EXCEEDED`) so KB matches are traceable, not just semantic-similarity guesses.
3. `src/task1_triage/` — the core pipeline:
   - Accept raw ticket (text or `{subject, body}` JSON)
   - Classify `product_area`, `category` (enum-constrained to the 8 known categories),
     `urgency` (P1-P4) — each with a short reasoning string
   - Run KB retrieval, attach best-matching doc(s) + why
   - Determine recommended responder team (rule mapping from product/category, e.g.
     Billing → Billing team, SecureVault+Auth → Security/Support tier-2)
   - Draft a first-response message grounded in the matched KB doc where one exists
4. Expose as both a plain Python function (`triage_ticket(ticket) -> TriageResult`) and
   a FastAPI endpoint (`app/main.py`, `POST /triage`).
5. Manually sanity-check against ~10 real tickets from the dataset, including a couple
   flagged as ambiguous, before moving on.

### Task 2 — TAM Account Health Summariser
1. `src/common/` — account/ticket loader that joins on `company`, filters to the last
   90 days relative to `AS_OF_DATE`, and handles accounts with zero tickets in-window
   or ticket `company` values with no account match.
2. **Non-LLM risk-signal extraction first:** sentence-split each ticket body +
   `escalation_notes`, score against a churn/escalation keyword & pattern set
   (e.g. competitor mentions, cancellation language, repeated P1s, negative CSAT).
   This produces verbatim candidate quotes *before* the LLM sees them — the LLM
   narrates/selects, it never generates the quote text itself. This guarantees every
   quote passes a `quote in ticket.body` substring check.
3. `src/task2_account_brief/` — LLM call (temperature 0, fixed seed) that takes the
   account record + windowed tickets + pre-extracted risk candidates and produces the
   3-section brief: executive summary, open risks & flagged issues (with quotes),
   recommended talking points.
4. Determinism check: run the same account twice, diff the output, confirm identical
   (or byte-identical after a normalising post-process if the runtime isn't fully
   deterministic on CPU).
5. Callable function (`generate_account_brief(account_id) -> AccountBrief`); reuse
   in the Streamlit bonus if we build it.

### Task 3 — Evaluation Harness
1. Hand-pick ≥5 test tickets per task from the real dataset (not synthetic-synthetic),
   including one deliberately ambiguous ticket (Task 1) and one account with sparse/
   no ticket history in the 90-day window (Task 2) as the required adversarial cases.
2. Rule-based checks (fast, deterministic, no LLM):
   - Task 1: valid enum values, urgency ∈ {P1-P4}, KB doc path exists if cited,
     classification vs. the dataset's own ground-truth label (held out, used only
     for eval, never fed to Task 1's prompt)
   - Task 2: every quoted string is a verbatim substring of its cited ticket,
     output is byte-identical across repeated runs (determinism), all 3 sections present
3. LLM-as-judge (used sparingly, for genuinely subjective quality — e.g. is the drafted
   first-response actually helpful/on-topic) — scored 0-1, clearly labelled as a softer
   signal in the report given the local model size.
4. `eval/run_eval.py` — runs all cases, produces `eval/reports/eval_report.md` (and/or
   `.json`) with pass/fail + score per case and a summary table.

### Task 4 — Design Note
Written after 1-3 are built, in `docs/design_note.md` (linked from this README),
covering: top 3 production failure modes + detection/mitigation, the latency-vs-quality
trade-off (planned: 3B vs 7-8B model, measured via the Task 3 harness rather than
asserted), PII/data-sensitivity handling (local-only inference is the headline point),
and a 10x-scale analysis.

### Bonus (pick 1-2 once core is solid)
Leaning toward: thin Streamlit UI for Task 2 (clear TAM value) and prompt versioning
(cheap to do properly throughout rather than bolt on later). Will revisit CI/streaming
if time allows.

---

## Design Note

See [`docs/design_note.md`](docs/design_note.md) *(pending — written after Tasks 1-3)*.