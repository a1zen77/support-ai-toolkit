"""
Eval Task 3 - pipeline.py tests.

Split into two groups:
- Fast, no-LLM tests: verify _resolve_selected_risks handles bad/malicious
  LLM output safely (out-of-range indices, empty selections) using a
  constructed BriefSynthesisOutput - no network call needed.
- Slow, real-LLM tests (marked `slow`): full generate_account_brief() runs
  against Ollama, on a small representative subset of accounts (not all
  50 - too slow for routine runs). Run explicitly with:
      pytest eval/test_pipeline.py -m slow -v
  or exclude them from a default run with:
      pytest eval/ -m "not slow" -v
"""

from __future__ import annotations

import pytest

from src.common.data_loader import get_tickets_for_company, load_accounts
from src.task2_account_brief.pipeline import _resolve_selected_risks, generate_account_brief
from src.task2_account_brief.risk_signals import extract_risk_candidates
from src.task2_account_brief.schemas import BriefSynthesisOutput, SelectedRisk


# ---------------------------------------------------------------------------
# Fast tests: index-resolution safety, no LLM involved
# ---------------------------------------------------------------------------

class TestResolveSelectedRisksSafety:
    """The LLM's candidate_index output is untrusted input. These tests
    verify the resolver never lets a bad index produce a fabricated or
    crashing RiskFlag."""

    def test_valid_index_resolves_correctly(self, all_accounts):
        account = next(a for a in all_accounts if a.escalation_notes)
        tickets = get_tickets_for_company(account.company, window_days=None)
        candidates = extract_risk_candidates(tickets, account)
        assert candidates, "test account must have at least one real candidate"

        output = BriefSynthesisOutput(
            executive_summary="test",
            selected_risks=[SelectedRisk(candidate_index=0, explanation="test explanation")],
            talking_points=[],
        )
        flags = _resolve_selected_risks(output, candidates, account)

        assert len(flags) == 1
        assert flags[0].quote == candidates[0].quote

    def test_out_of_range_index_is_dropped_not_crashed(self, all_accounts):
        account = next(a for a in all_accounts if a.escalation_notes)
        tickets = get_tickets_for_company(account.company, window_days=None)
        candidates = extract_risk_candidates(tickets, account)

        output = BriefSynthesisOutput(
            executive_summary="test",
            selected_risks=[
                SelectedRisk(candidate_index=999, explanation="hallucinated index"),
            ],
            talking_points=[],
        )
        # Should not raise - out-of-range index is silently dropped.
        flags = _resolve_selected_risks(output, candidates, account)
        assert flags == []

    def test_negative_index_is_dropped_not_crashed(self, all_accounts):
        account = next(a for a in all_accounts if a.escalation_notes)
        tickets = get_tickets_for_company(account.company, window_days=None)
        candidates = extract_risk_candidates(tickets, account)

        output = BriefSynthesisOutput(
            executive_summary="test",
            selected_risks=[SelectedRisk(candidate_index=-1, explanation="negative index")],
            talking_points=[],
        )
        flags = _resolve_selected_risks(output, candidates, account)
        assert flags == []

    def test_mixed_valid_and_invalid_indices_keeps_only_valid(self, all_accounts):
        account = next(a for a in all_accounts if len(extract_risk_candidates(
            get_tickets_for_company(a.company, window_days=None), a
        )) >= 2)
        tickets = get_tickets_for_company(account.company, window_days=None)
        candidates = extract_risk_candidates(tickets, account)

        output = BriefSynthesisOutput(
            executive_summary="test",
            selected_risks=[
                SelectedRisk(candidate_index=0, explanation="valid"),
                SelectedRisk(candidate_index=500, explanation="hallucinated"),
                SelectedRisk(candidate_index=1, explanation="also valid"),
            ],
            talking_points=[],
        )
        flags = _resolve_selected_risks(output, candidates, account)

        assert len(flags) == 2
        resolved_quotes = {f.quote for f in flags}
        assert resolved_quotes == {candidates[0].quote, candidates[1].quote}

    def test_empty_candidate_list_with_selection_drops_everything(self, all_accounts):
        account = all_accounts[0]
        output = BriefSynthesisOutput(
            executive_summary="test",
            selected_risks=[SelectedRisk(candidate_index=0, explanation="no candidates exist")],
            talking_points=[],
        )
        flags = _resolve_selected_risks(output, candidates=[], account=account)
        assert flags == []

    def test_no_selections_returns_empty_flags(self, all_accounts):
        account = all_accounts[0]
        tickets = get_tickets_for_company(account.company, window_days=None)
        candidates = extract_risk_candidates(tickets, account)

        output = BriefSynthesisOutput(
            executive_summary="test", selected_risks=[], talking_points=[]
        )
        flags = _resolve_selected_risks(output, candidates, account)
        assert flags == []


# ---------------------------------------------------------------------------
# Slow tests: real LLM calls via Ollama, small account subset
# ---------------------------------------------------------------------------

# A fixed, small set of companies chosen to cover different shapes: one with
# escalation notes + candidates (Omni), plus two more for variety. Kept
# small deliberately - this hits a local 7B model 2x per company (brief +
# determinism re-run), so don't expand this to all 50 without good reason.
_SLOW_TEST_COMPANIES = ["Omni Consumer Products"]


@pytest.mark.slow
class TestFullPipelineWithRealLLM:
    @pytest.mark.parametrize("company", _SLOW_TEST_COMPANIES)
    def test_end_to_end_brief_has_verbatim_quotes(self, company):
        brief = generate_account_brief(company=company, window_days=None)

        tickets = get_tickets_for_company(company, window_days=None)
        tickets_by_id = {t.ticket_id: t for t in tickets}

        from src.common.data_loader import get_account_by_company
        account = get_account_by_company(company)
        escalation_text = "\n".join(account.escalation_notes)

        for flag in brief.risks_and_flags:
            if flag.source == "ticket_body":
                assert flag.quote in tickets_by_id[flag.ticket_id].body, (
                    f"Non-verbatim quote in final brief for {company}: {flag.quote!r}"
                )
            elif flag.source == "escalation_notes":
                assert flag.quote in escalation_text, (
                    f"Non-verbatim quote in final brief for {company}: {flag.quote!r}"
                )

    @pytest.mark.parametrize("company", _SLOW_TEST_COMPANIES)
    def test_determinism_same_input_same_output(self, company):
        run1 = generate_account_brief(company=company, window_days=None)
        run2 = generate_account_brief(company=company, window_days=None)
        assert run1.model_dump(mode="json") == run2.model_dump(mode="json")

    def test_unknown_company_raises_value_error(self):
        with pytest.raises(ValueError, match="No account found"):
            generate_account_brief(company="Definitely Not A Real Company Inc.")

    def test_unknown_account_id_raises_value_error(self):
        with pytest.raises(ValueError, match="No account found"):
            generate_account_brief(account_id="ACC-99999999")