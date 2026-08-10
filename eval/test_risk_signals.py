"""
Eval Task 3 - risk_signals.py tests. Priority #1: the verbatim-quote
guarantee, since Task 2's brief explicitly requires flags to be justified
by a direct quote, and small local LLMs are known to paraphrase under
pressure - this is the check that would catch a regression if anyone
(including future-us) ever lets the LLM touch quote text.
"""

from __future__ import annotations

import pytest

from src.common.schemas import Account, Ticket
from src.task2_account_brief.risk_signals import (
    extract_risk_candidates,
    split_sentences,
)


class TestQuoteVerbatim:
    """Every RiskCandidate.quote must be an exact substring of its claimed
    source text. This is the single most important guarantee in Task 2."""

    def test_all_candidates_verbatim_across_full_dataset(
        self, account_ticket_pairs: list[tuple[Account, list[Ticket]]]
    ):
        failures: list[str] = []
        total_candidates = 0

        for account, tickets in account_ticket_pairs:
            candidates = extract_risk_candidates(tickets, account)
            total_candidates += len(candidates)

            tickets_by_id = {t.ticket_id: t for t in tickets}
            escalation_text = "\n".join(account.escalation_notes)

            for c in candidates:
                if c.source == "ticket_body":
                    source_text = tickets_by_id[c.ticket_id].body
                elif c.source == "escalation_notes":
                    source_text = escalation_text
                else:
                    failures.append(
                        f"{account.company}: unknown source {c.source!r} "
                        f"on candidate {c.quote!r}"
                    )
                    continue

                if c.quote not in source_text:
                    failures.append(
                        f"{account.company} / ticket={c.ticket_id or 'escalation_notes'}: "
                        f"quote {c.quote!r} NOT found verbatim in source"
                    )

        assert total_candidates > 0, (
            "Sanity check failed: zero candidates found across the entire "
            "dataset - this almost certainly means the patterns are broken, "
            "not that the data is clean (see earlier manual coverage check)."
        )
        assert not failures, (
            f"{len(failures)} non-verbatim quote(s) found:\n" + "\n".join(failures)
        )

    def test_no_duplicate_quotes_within_same_category_per_account(
        self, account_ticket_pairs: list[tuple[Account, list[Ticket]]]
    ):
        """extract_risk_candidates dedupes identical (category, sentence)
        pairs - verify that dedup is actually holding, not just present in
        the code but silently broken."""
        for account, tickets in account_ticket_pairs:
            candidates = extract_risk_candidates(tickets, account)
            seen = set()
            for c in candidates:
                key = (c.category, c.source, c.ticket_id, c.quote)
                assert key not in seen, (
                    f"{account.company}: duplicate candidate found for "
                    f"category={c.category} quote={c.quote!r}"
                )
                seen.add(key)


class TestSplitSentences:
    """Unit tests for the sentence splitter in isolation, since every
    downstream guarantee depends on it slicing cleanly."""

    def test_empty_string_returns_empty_list(self):
        assert split_sentences("") == []
        assert split_sentences("   ") == []

    def test_single_sentence_no_split(self):
        result = split_sentences("This is one sentence.")
        assert result == ["This is one sentence."]

    def test_multiple_sentences_split_correctly(self):
        text = "First sentence. Second sentence! Third sentence?"
        result = split_sentences(text)
        assert result == ["First sentence.", "Second sentence!", "Third sentence?"]

    def test_every_returned_sentence_is_verbatim_substring(self):
        """The property that actually matters downstream: regardless of
        how splitting handles edge cases (abbreviations, etc.), every
        piece it returns must be reconstructable from the original text."""
        text = (
            "We've outgrown our current Enterprise plan. Please advise on "
            "next steps re: upgrade options, e.g. SSO support."
        )
        for sentence in split_sentences(text):
            assert sentence in text

    def test_whitespace_only_fragments_are_dropped(self):
        text = "First.   \n\n  Second."
        result = split_sentences(text)
        assert all(s.strip() == s and s for s in result)


class TestExtractRiskCandidatesEdgeCases:
    def test_no_crash_on_account_with_no_escalation_notes(
        self, all_accounts: list[Account]
    ):
        from src.common.data_loader import get_tickets_for_company

        account = next(a for a in all_accounts if not a.escalation_notes)
        tickets = get_tickets_for_company(account.company, window_days=None)
        # Should not raise, regardless of candidate count.
        extract_risk_candidates(tickets, account)

    def test_no_crash_on_account_with_zero_tickets(self, all_accounts: list[Account]):
        # window_days=1 on a dataset that ends 2026-05-22 should yield very
        # few or zero tickets for most accounts - verifies extraction
        # doesn't assume a non-empty ticket list.
        from src.common.data_loader import get_tickets_for_company

        account = all_accounts[0]
        tickets = get_tickets_for_company(account.company, window_days=1)
        extract_risk_candidates(tickets, account)  # should not raise