"""
Task 2 (Account Health Summariser) eval cases. Reuses the same
verbatim-quote guarantee already covered exhaustively in
eval/test_risk_signals.py, but here at the full pipeline/LLM-output level,
plus determinism, artifact-leakage regression guards, and an LLM-judge
groundedness check. Two adversarial cases: a zero-signal account, and a
nonexistent account handled gracefully (not just "doesn't crash").
"""

from __future__ import annotations

from src.common.data_loader import get_account_by_company, get_tickets_for_company, load_accounts
from src.task2_account_brief.pipeline import generate_account_brief
from src.task2_account_brief.risk_signals import extract_risk_candidates
from eval.harness_core import EvalCase, ScoreResult
from eval.task1_cases import _llm_judge  # reuse the same judge helper

_TEST_COMPANY_WITH_SIGNAL = "Omni Consumer Products"


# ---------------------------------------------------------------------------
# Rule-based cases
# ---------------------------------------------------------------------------

def _case_verbatim_quotes_end_to_end() -> EvalCase:
    def score(brief):
        account = get_account_by_company(_TEST_COMPANY_WITH_SIGNAL)
        tickets = get_tickets_for_company(_TEST_COMPANY_WITH_SIGNAL, window_days=None)
        tickets_by_id = {t.ticket_id: t for t in tickets}
        escalation_text = "\n".join(account.escalation_notes)

        bad = []
        for flag in brief.risks_and_flags:
            source_text = (
                tickets_by_id[flag.ticket_id].body
                if flag.source == "ticket_body"
                else escalation_text
            )
            if flag.quote not in source_text:
                bad.append(flag.quote)

        if bad:
            return ScoreResult(
                passed=False, score=0.0,
                reasoning=f"{len(bad)} non-verbatim quote(s) in final brief: {bad}",
            )
        return ScoreResult(
            passed=True, score=1.0,
            reasoning=f"All {len(brief.risks_and_flags)} risk flag quote(s) verified verbatim in source",
        )

    return EvalCase(
        id="task2_verbatim_quotes_end_to_end",
        task="task2_account_brief",
        description="Every RiskFlag.quote in the final brief must be an exact substring of its source",
        run=lambda: generate_account_brief(company=_TEST_COMPANY_WITH_SIGNAL, window_days=None),
        score=score,
    )


def _case_determinism() -> EvalCase:
    def run():
        run1 = generate_account_brief(company=_TEST_COMPANY_WITH_SIGNAL, window_days=None)
        run2 = generate_account_brief(company=_TEST_COMPANY_WITH_SIGNAL, window_days=None)
        return (run1, run2)

    def score(output):
        run1, run2 = output
        d1, d2 = run1.model_dump(mode="json"), run2.model_dump(mode="json")
        if d1 != d2:
            diffs = [k for k in d1 if d1[k] != d2[k]]
            return ScoreResult(
                passed=False, score=0.0,
                reasoning=f"Two runs on identical input diverged in fields: {diffs}",
            )
        return ScoreResult(passed=True, score=1.0, reasoning="Two runs on identical input produced byte-identical output")

    return EvalCase(
        id="task2_determinism",
        task="task2_account_brief",
        description="Same account input twice must produce byte-identical AccountBrief (temp=0, seed=42)",
        run=run,
        score=score,
    )


def _case_no_llm_formatting_artifacts_in_talking_points() -> EvalCase:
    def score(brief):
        bad = [tp for tp in brief.talking_points if tp.strip().startswith(("-", "*", "•")) or tp.strip()[:2].rstrip(".").isdigit()]
        if bad:
            return ScoreResult(
                passed=False, score=0.3,
                reasoning=f"talking_points contain leading bullet/number artifacts (regression, see prompts.py changelog): {bad}",
            )
        if not brief.talking_points:
            return ScoreResult(passed=False, score=0.0, reasoning="talking_points is empty - expected 2-5 items per prompt spec")
        return ScoreResult(passed=True, score=1.0, reasoning=f"All {len(brief.talking_points)} talking points are clean plain sentences")

    return EvalCase(
        id="task2_talking_points_no_artifacts",
        task="task2_account_brief",
        description="Regression guard: talking_points must be plain sentences, no leading dash/bullet/number",
        run=lambda: generate_account_brief(company=_TEST_COMPANY_WITH_SIGNAL, window_days=None),
        score=score,
    )


def _case_executive_summary_references_real_data() -> EvalCase:
    """Rule-based groundedness proxy: the summary should reference at least
    one real figure from the account facts (ticket count, health status
    wording, etc.) rather than being generic boilerplate."""

    def score(brief):
        account = get_account_by_company(_TEST_COMPANY_WITH_SIGNAL)
        summary_lower = brief.executive_summary.lower()

        grounding_signals = [
            str(brief.tickets_considered) in brief.executive_summary,
            account.health_status.lower() in summary_lower,
            account.usage_trend.lower() in summary_lower,
        ]
        hits = sum(grounding_signals)

        if hits == 0:
            return ScoreResult(
                passed=False, score=0.2,
                reasoning="Executive summary references none of: ticket count, health status, usage trend - looks generic/ungrounded",
            )
        return ScoreResult(
            passed=True, score=min(1.0, 0.5 + 0.25 * hits),
            reasoning=f"Executive summary references {hits}/3 checked grounding signals from real account data",
        )

    return EvalCase(
        id="task2_executive_summary_grounded",
        task="task2_account_brief",
        description="Executive summary should reference real account facts, not generic boilerplate",
        run=lambda: generate_account_brief(company=_TEST_COMPANY_WITH_SIGNAL, window_days=None),
        score=score,
    )


# ---------------------------------------------------------------------------
# LLM-as-judge case
# ---------------------------------------------------------------------------

def _case_risk_explanations_are_own_words_judge() -> EvalCase:
    def score(brief):
        if not brief.risks_and_flags:
            return ScoreResult(
                passed=True, score=1.0,
                reasoning="No risk flags were selected this run - nothing to judge (not a failure)",
            )

        flag = brief.risks_and_flags[0]
        question = (
            f'A risk flag has this verbatim source quote: "{flag.quote}"\n\n'
            f'And this LLM-written explanation of why it matters: "{flag.explanation}"\n\n'
            f"Does the explanation add genuine interpretive context (why this matters for "
            f"account health) rather than just restating or lightly rephrasing the quote?"
        )
        return _llm_judge(question)

    return EvalCase(
        id="task2_risk_explanation_adds_value_judge",
        task="task2_account_brief",
        description="LLM-judge: risk explanation interprets the quote rather than just restating it",
        run=lambda: generate_account_brief(company=_TEST_COMPANY_WITH_SIGNAL, window_days=None),
        score=score,
    )


# ---------------------------------------------------------------------------
# Adversarial cases
# ---------------------------------------------------------------------------

def _case_adversarial_zero_signal_account() -> EvalCase:
    """Find a real account with zero risk candidates - verifies the
    pipeline doesn't fabricate risks when none exist, and doesn't crash on
    an empty escalation_notes/candidate list."""

    def run():
        accounts = load_accounts()
        for account in accounts:
            tickets = get_tickets_for_company(account.company, window_days=None)
            if not extract_risk_candidates(tickets, account):
                return generate_account_brief(company=account.company, window_days=None)
        raise RuntimeError("No zero-candidate account found in dataset - adversarial case can't run")

    def score(brief):
        if brief.risks_and_flags:
            return ScoreResult(
                passed=False, score=0.0,
                reasoning=(
                    f"Account had zero real risk candidates but brief contains "
                    f"{len(brief.risks_and_flags)} risk flag(s) - likely fabricated"
                ),
            )
        return ScoreResult(
            passed=True, score=1.0,
            reasoning="Correctly produced zero risk flags for an account with zero real candidates - no fabrication",
        )

    return EvalCase(
        id="task2_adversarial_zero_signal_account",
        task="task2_account_brief",
        description="ADVERSARIAL: account with zero risk candidates must not have fabricated risk flags",
        run=run,
        score=score,
        is_adversarial=True,
    )


def _case_adversarial_unknown_account_graceful_failure() -> EvalCase:
    """Verifies the failure mode itself is correct (ValueError with a clear
    message), not just that *something* gets raised. run() catches the
    expected exception internally so the harness scores the failure
    behavior rather than treating it as a crash."""

    def run():
        try:
            generate_account_brief(company="Definitely Not A Real Company Inc.")
            return {"raised": None}
        except ValueError as e:
            return {"raised": "ValueError", "message": str(e)}
        except Exception as e:
            return {"raised": type(e).__name__, "message": str(e)}

    def score(output):
        if output["raised"] is None:
            return ScoreResult(
                passed=False, score=0.0,
                reasoning="Unknown company silently succeeded instead of raising - should fail loudly",
            )
        if output["raised"] != "ValueError":
            return ScoreResult(
                passed=False, score=0.3,
                reasoning=f"Raised {output['raised']} instead of ValueError - wrong failure mode, harder for callers to handle correctly",
            )
        if "No account found" not in output["message"]:
            return ScoreResult(
                passed=False, score=0.6,
                reasoning=f"Raised correct ValueError type but message isn't clear/actionable: {output['message']!r}",
            )
        return ScoreResult(
            passed=True, score=1.0,
            reasoning="Unknown company raises a clear, correctly-typed ValueError with an actionable message",
        )

    return EvalCase(
        id="task2_adversarial_unknown_account",
        task="task2_account_brief",
        description="ADVERSARIAL: nonexistent company must fail gracefully with a clear ValueError, not crash or silently succeed",
        run=run,
        score=score,
        is_adversarial=True,
    )


def get_task2_cases() -> list[EvalCase]:
    return [
        _case_verbatim_quotes_end_to_end(),
        _case_determinism(),
        _case_no_llm_formatting_artifacts_in_talking_points(),
        _case_executive_summary_references_real_data(),
        _case_risk_explanations_are_own_words_judge(),
        _case_adversarial_zero_signal_account(),
        _case_adversarial_unknown_account_graceful_failure(),
    ]