# Design Note

## Failure modes

**1. Product misclassification on zero-signal tickets.** The eval harness
caught this directly: a billing/seat-count ticket that never names a
product caused `classify_v3` to guess a different product on every retry
attempt, exhausting all 3 attempts and raising `LLMGenerationError`. A
follow-up fix (`classify_v4`) then surfaced a second bug — the model
started writing `"Billing"` (a category value) into `product_area`, a
field where no product has a "Billing" area. Detection: the eval harness's
`task1_adversarial_billing_no_product_signal` case now runs this exact
scenario on every eval pass, so a regression would be caught immediately
rather than in production. Mitigation: the prompt now explicitly
distinguishes category from product_area and instructs the model to
commit to its single best guess under total ambiguity rather than
re-guessing across retries.

**2. LLM quote fabrication in risk flags.** Small local models are known
to paraphrase under pressure, which is disqualifying for a feature whose
entire premise is "justify this flag with a direct quote." Mitigation is
structural, not just prompted: quotes are extracted by regex/keyword
matching over verbatim ticket text *before* the LLM is ever called; the
LLM's output schema (`BriefSynthesisOutput`) has no field capable of
holding quote text at all — it can only select a candidate by index and
write its own explanation. Detection: a hard `quote in source_text`
assertion runs in the eval harness across the full 50-account dataset on
every run, plus a dataset-wide pytest suite (`eval/test_risk_signals.py`).

**3. Unreliable `account_id` join.** Only 4 of 500 tickets have an
`account_id` matching `accounts.json`, and those 4 are coincidental
mismatches. Joining on `company` instead is 100% reliable across the
dataset, but this is a data-quality issue that would need real
investigation before production use — a `company` string match is far
more fragile than a stable ID (case sensitivity, renames, duplicates).
Mitigation for now: documented explicitly as a known constraint; detection
in production would need a join-integrity check that alerts if match rate
drops below expected thresholds.

## Latency vs quality trade-off

KB grounding uses two thresholds: matches ≥0.35 similarity are surfaced to
the agent for reference, but only matches ≥0.5 are allowed to ground the
LLM's drafted response. This sacrifices response coverage — some tickets
get an honest "no strong match found" instead of a lower-confidence draft
— in exchange for not fabricating specific-sounding but wrong instructions
from weak semantic matches (an earlier bug we hit at ~0.38 similarity).
Determinism (temperature=0, fixed seed, no streaming) is also a
latency-for-reproducibility trade: it makes exact-match eval assertions
possible but rules out the perceived-speed benefit of token streaming. If
latency were the hard constraint, I'd relax the grounding floor slightly,
cap retries on structured-output failures at 1 instead of 3, and
reintroduce streaming — accepting non-deterministic wording per call while
still enforcing the verbatim-quote guarantee structurally (that guarantee
doesn't depend on determinism).

## Data sensitivity

No external API calls exist anywhere in the pipeline. Classification, KB
retrieval embeddings, and brief synthesis all run through a local Ollama
instance and a local sentence-transformers model — ticket and account
text, which may contain PII, never leaves the machine. This was a
deliberate constraint from the start, not a retrofit, and is documented in
`.env.example` explicitly so it's visible to anyone auditing the setup.

## Scaling (10x ticket volume)

The first thing to break is KB indexing cost, not ticket volume itself —
the KB stays small regardless of ticket count, so that's fine. The real
bottleneck is sequential Ollama calls: each triage or brief-synthesis call
takes 10-50+ seconds locally, and nothing here is batched or parallelized.
At 5,000 tickets, a naive sequential run becomes hours, not minutes. The
retry-on-invalid-JSON logic (up to 3 attempts per call) also compounds
linearly with volume. Second-order pressure: the `company`-based join
(already a known fragility at 50 accounts) gets riskier as more
tickets/accounts are added with real-world messier naming. At 10x scale
I'd prioritize concurrent request batching against Ollama (or a properly
served model with request queuing) and revisit the account join key before
either the LLM throughput or the join integrity becomes the actual
production incident.