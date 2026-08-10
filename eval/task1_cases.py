"""
Task 1 (Triage Agent) eval cases. Mix of rule-based (fast, deterministic)
and LLM-as-judge (qualitative) scoring, per the assignment's "rule-based,
LLM-as-judge, or both" requirement. One adversarial case included
(ambiguous/incomplete ticket) per the spec.
"""

from __future__ import annotations

from src.common.ollama_client import generate_text
from src.common.schemas import TicketInput
from src.task1_triage.pipeline import triage_ticket
from eval.harness_core import EvalCase, ScoreResult

# ---------------------------------------------------------------------------
# LLM-as-judge helper
# ---------------------------------------------------------------------------

def _llm_judge(question: str) -> ScoreResult:
    """
    Asks the judge model a yes/no/partial quality question, expects a
    strict one-line response we can parse. Used for qualitative checks
    that a rule can't easily capture (tone, relevance, groundedness).
    """
    judge_prompt = (
        f"{question}\n\n"
        "Respond with EXACTLY one line in this format, no other text:\n"
        "VERDICT: <YES|PARTIAL|NO> | SCORE: <a number 0.0-1.0> | REASON: <one short sentence>"
    )
    raw = generate_text(judge_prompt, temperature=0.0)

    try:
        parts = {p.split(":", 1)[0].strip(): p.split(":", 1)[1].strip() for p in raw.split("|")}
        verdict = parts["VERDICT"].upper()
        score = float(parts["SCORE"])
        reason = parts["REASON"]
    except (KeyError, ValueError, IndexError):
        return ScoreResult(
            passed=False, score=0.0,
            reasoning=f"Judge response unparseable: {raw!r}",
        )

    passed = verdict in ("YES", "PARTIAL")
    score = max(0.0, min(1.0, score))
    return ScoreResult(passed=passed, score=score, reasoning=f"[judge: {verdict}] {reason}")


# ---------------------------------------------------------------------------
# Rule-based cases
# ---------------------------------------------------------------------------

def _case_clear_p1_urgency() -> EvalCase:
    ticket = TicketInput(
        subject="Production outage - all users locked out",
        body=(
            "Since 9am this morning, ALL users at our company are getting "
            "AUTH_TOKEN_EXPIRED errors and cannot log in via SSO. This is "
            "affecting our entire production environment. We need this "
            "fixed immediately."
        ),
    )

    def score(output):
        if output.urgency.value != "P1":
            return ScoreResult(
                passed=False, score=0.2,
                reasoning=f"Expected P1 for a clear production-down outage, got {output.urgency.value}",
            )
        return ScoreResult(passed=True, score=1.0, reasoning="Correctly classified as P1")

    return EvalCase(
        id="task1_clear_p1_urgency",
        task="task1_triage",
        description="Unambiguous production outage should classify as P1",
        run=lambda: triage_ticket(ticket),
        score=score,
    )


def _case_billing_routes_to_billing_team() -> EvalCase:
    ticket = TicketInput(
        subject="Question about our invoice",
        body="We were charged for 50 seats but only have 30 active users. Can you clarify the billing logic?",
    )

    def score(output):
        if output.category.value != "Billing":
            return ScoreResult(
                passed=False, score=0.3,
                reasoning=f"Expected category=Billing, got {output.category.value}",
            )
        if "Billing" not in output.recommended_team:
            return ScoreResult(
                passed=False, score=0.5,
                reasoning=f"Category correct but routing didn't go to Billing Team: {output.recommended_team}",
            )
        return ScoreResult(passed=True, score=1.0, reasoning="Correctly categorized and routed to Billing Team")

    return EvalCase(
        id="task1_billing_routing",
        task="task1_triage",
        description="Billing question should classify as Billing and route to Billing Team",
        run=lambda: triage_ticket(ticket),
        score=score,
    )


def _case_error_code_grounds_kb_match() -> EvalCase:
    ticket = TicketInput(
        subject="Pipeline monitoring broken",
        body="We're seeing DEPENDENCY_UNAVAILABLE errors in the Pipeline Monitoring module for all users.",
    )

    def score(output):
        exact_matches = [m for m in output.kb_matches if "exact error code match" in m.matched_reason]
        if not exact_matches:
            return ScoreResult(
                passed=False, score=0.0,
                reasoning="Expected an exact error-code KB match for DEPENDENCY_UNAVAILABLE, found none",
            )
        return ScoreResult(
            passed=True, score=1.0,
            reasoning=f"Found exact KB match: {exact_matches[0].doc_path}",
        )

    return EvalCase(
        id="task1_kb_exact_error_code_match",
        task="task1_triage",
        description="A ticket citing a known error code should surface an exact-match KB doc",
        run=lambda: triage_ticket(ticket),
        score=score,
    )


def _case_product_area_schema_valid() -> EvalCase:
    """Structural check: product_area must be non-blank and belong to the
    classified product's valid area list - this was a real bug we fixed
    during Task 1 development (see PROMPT_CHANGELOG, classify_v2)."""
    ticket = TicketInput(
        subject="Dashboard is blank",
        body="Our dashboard has been blank for two days and nobody on the team can see reports.",
    )

    def score(output):
        from src.task1_triage.prompts import PRODUCT_AREAS

        if not output.product_area or not output.product_area.strip():
            return ScoreResult(passed=False, score=0.0, reasoning="product_area is blank")

        valid_areas = PRODUCT_AREAS.get(output.product or "", [])
        if output.product_area not in valid_areas:
            return ScoreResult(
                passed=False, score=0.3,
                reasoning=f"product_area {output.product_area!r} not valid for product {output.product!r}",
            )
        return ScoreResult(passed=True, score=1.0, reasoning="product_area is non-blank and schema-valid")

    return EvalCase(
        id="task1_product_area_never_blank",
        task="task1_triage",
        description="Regression guard: product_area must never be blank (classify_v2 fix)",
        run=lambda: triage_ticket(ticket),
        score=score,
    )


# ---------------------------------------------------------------------------
# LLM-as-judge case
# ---------------------------------------------------------------------------

def _case_draft_response_is_grounded_not_fabricated() -> EvalCase:
    ticket = TicketInput(
        subject="Webhook delivery failing",
        body="Our AnalyticsHub webhooks are not being delivered to HubSpot. Endpoint is reachable, secret is correct.",
    )

    def score(output):
        question = (
            f"A support agent drafted this first-response message to a customer:\n\n"
            f'"{output.draft_response}"\n\n'
            f"The customer's issue was: webhooks not delivering to HubSpot despite a "
            f"reachable endpoint and correct secret.\n\n"
            f"Does this response stay professional, avoid promising a specific fix "
            f"timeline it can't know, and avoid inventing technical details that "
            f"weren't in the customer's message?"
        )
        return _llm_judge(question)

    return EvalCase(
        id="task1_draft_response_quality_judge",
        task="task1_triage",
        description="LLM-judge: draft response is professional and doesn't fabricate unsupported specifics",
        run=lambda: triage_ticket(ticket),
        score=score,
    )


# ---------------------------------------------------------------------------
# Adversarial case
# ---------------------------------------------------------------------------

def _case_adversarial_empty_body() -> EvalCase:
    """Incomplete input: empty body, near-empty subject. Should not crash,
    and should not hallucinate specific technical details it has no basis
    for."""
    ticket = TicketInput(subject="help", body="")

    def score(output):
        # Primary bar: pipeline didn't crash and returned a valid TriageResult
        # (verified implicitly by reaching this point). Secondary bar: it
        # didn't fabricate an oddly specific, confident diagnosis from
        # nothing.
        vague_ok_phrases = ["more information", "more detail", "clarify", "unable to determine", "please provide"]
        draft_lower = output.draft_response.lower()
        acknowledges_ambiguity = any(p in draft_lower for p in vague_ok_phrases)

        if not acknowledges_ambiguity:
            return ScoreResult(
                passed=True, score=0.5,
                reasoning=(
                    "Pipeline handled empty input without crashing (primary bar met), "
                    "but draft response didn't explicitly ask for more information "
                    "given how little context it had (secondary, softer bar)."
                ),
            )
        return ScoreResult(
            passed=True, score=1.0,
            reasoning="Handled empty/near-empty input without crashing and appropriately asked for more detail",
        )

    return EvalCase(
        id="task1_adversarial_empty_body",
        task="task1_triage",
        description="ADVERSARIAL: near-empty ticket (subject='help', body='') should not crash or fabricate specifics",
        run=lambda: triage_ticket(ticket),
        score=score,
        is_adversarial=True,
    )


def get_task1_cases() -> list[EvalCase]:
    return [
        _case_clear_p1_urgency(),
        _case_billing_routes_to_billing_team(),
        _case_error_code_grounds_kb_match(),
        _case_product_area_schema_valid(),
        _case_draft_response_is_grounded_not_fabricated(),
        _case_adversarial_empty_body(),
    ]