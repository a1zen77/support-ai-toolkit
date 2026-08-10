"""
Non-LLM risk signal extraction. Splits ticket bodies / escalation_notes into
sentences and scores them against keyword patterns per RiskCategory. Every
resulting RiskCandidate.quote is a verbatim substring of the source text -
this is enforced by construction (we slice from the split sentences, never
reconstruct or paraphrase) and is asserted again in the eval harness later.
"""

from __future__ import annotations

import re

from src.common.schemas import Account, Ticket
from src.task2_account_brief.schemas import RiskCandidate, RiskCategory

# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------
# Deliberately simple: split on sentence-ending punctuation followed by
# whitespace/EOL. Good enough for support-ticket prose; doesn't need to
# handle abbreviations perfectly since a slightly-off boundary still yields
# a verbatim substring (just maybe a merged sentence), which is all the
# "quote in source text" guarantee requires.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = _SENTENCE_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Keyword patterns per category
# ---------------------------------------------------------------------------
# Each pattern is a compiled case-insensitive regex. We keep the ORIGINAL
# matched span's containing sentence as the quote - never the pattern itself.
_PATTERNS: dict[RiskCategory, list[re.Pattern]] = {
    RiskCategory.CHURN_INTENT: [
        re.compile(r"\bcancel(l?ing)?\s+(our|my|the)\s+(subscription|contract|account|plan)\b", re.I),
        re.compile(r"\b(consider(ing)?|evaluat(ing|e))\s+.{0,40}\b(compet(itor|ing|itors)|alternative)\b", re.I),
        re.compile(r"\bnot\s+renew(ing)?\b", re.I),
        re.compile(r"\bwe\s+(are|'re)\s+(done|out|finished)\s+with\b", re.I),
        re.compile(r"\blooking\s+at\s+(other\s+)?(vendors|alternatives|options)\b", re.I),
        re.compile(r"\bvendor\s+evaluation\b", re.I),
    ],
    RiskCategory.ESCALATION: [
        re.compile(r"\b(speak|talk)\s+to\s+(a|your)\s+manager\b", re.I),
        re.compile(r"\bescalat(e|ing|ed|ion)\b", re.I),
        re.compile(r"\bformal\s+complaint\b", re.I),
        re.compile(r"\bneed(s)?\s+to\s+be\s+escalated\b", re.I),
        re.compile(r"\b\d+\s+consecutive\s+(P1|P2|critical)\b", re.I),
    ],
    RiskCategory.REPEATED_ISSUE: [
        re.compile(r"\b(again|still\s+(not|hasn't|isn't))\b", re.I),
        re.compile(r"\b(third|fourth|multiple|several)\s+time(s)?\b", re.I),
        re.compile(r"\bkeeps?\s+happening\b", re.I),
        re.compile(r"\bsame\s+issue\s+(as\s+before|again)\b", re.I),
        re.compile(r"\b\d+\s+(P1|P2)\s+tickets\s+in\s+the\s+last\s+\d+\s+days\b", re.I),
    ],
    RiskCategory.SLA_BREACH: [
        re.compile(r"\b(missed|breach(ed)?)\s+(the\s+)?(sla|deadline|response\s+time)\b", re.I),
        re.compile(r"\b(no|still\s+no)\s+response\s+(in|for|after)\s+\d+\s*(hours?|days?)\b", re.I),
        re.compile(r"\bpromised\s+.{0,30}\b(and|but)\s+(never|didn't|did\s+not)\b", re.I),
    ],
    RiskCategory.EXECUTIVE_ATTENTION: [
        re.compile(r"\b(our\s+)?(ceo|cto|coo|vp|vice\s+president|director|decision\s+maker)\s+(is|has|wants|asked|considering)\b", re.I),
        re.compile(r"\bexecutive\s+(team|sponsor|leadership)\b", re.I),
        re.compile(r"\bleadership\s+is\s+(asking|concerned|involved)\b", re.I),
    ],
    RiskCategory.DISSATISFACTION: [
        re.compile(r"\b(extremely|very|really)\s+(frustrat(ed|ing)|disappoint(ed|ing)|unhappy)\b", re.I),
        re.compile(r"\bunacceptable\b", re.I),
        re.compile(r"\bthis\s+is\s+(ridiculous|unacceptable|a\s+joke)\b", re.I),
        re.compile(r"\blosing\s+(confidence|trust|patience)\b", re.I),
    ],
    RiskCategory.COMPETITOR_MENTION: [
        re.compile(r"\bcompet(itor|itors|ing)\b", re.I),
        re.compile(r"\balternative(s)?\s+(product|vendor|solution)\b", re.I),
    ],
}


def _extract_from_text(
    text: str,
    source: str,
    ticket_id: str | None,
) -> list[RiskCandidate]:
    candidates: list[RiskCandidate] = []
    seen_quotes: set[str] = set()  # dedup identical sentences matched by multiple patterns

    for idx, sentence in enumerate(split_sentences(text)):
        for category, patterns in _PATTERNS.items():
            for pattern in patterns:
                m = pattern.search(sentence)
                if not m:
                    continue
                dedup_key = f"{category.value}:{sentence}"
                if dedup_key in seen_quotes:
                    continue
                seen_quotes.add(dedup_key)
                candidates.append(
                    RiskCandidate(
                        ticket_id=ticket_id,
                        quote=sentence,
                        source=source,
                        category=category,
                        matched_pattern=m.group(0),
                        sentence_index=idx,
                    )
                )
                break  # one match per category per sentence is enough

    return candidates


def extract_risk_candidates(
    tickets: list[Ticket],
    account: Account,
) -> list[RiskCandidate]:
    """
    Scans ticket bodies (verbatim) and account-level escalation_notes
    (verbatim) for risk-indicating language. Returns ALL matches - the
    caller (LLM synthesis step) selects which to surface, but never edits
    quote text.
    """
    candidates: list[RiskCandidate] = []

    for ticket in tickets:
        candidates.extend(
            _extract_from_text(ticket.body, source="ticket_body", ticket_id=ticket.ticket_id)
        )

    for note in account.escalation_notes:
        candidates.extend(
            _extract_from_text(note, source="escalation_notes", ticket_id=None)
        )

    return candidates


def assert_all_quotes_verbatim(
    candidates: list[RiskCandidate],
    tickets: list[Ticket],
    account: Account,
) -> None:
    """
    Hard verification: every candidate's quote must be an exact substring
    of its claimed source. Raises AssertionError otherwise. This is the
    same check the eval harness (Task 3) will run independently.
    """
    tickets_by_id = {t.ticket_id: t for t in tickets}
    for c in candidates:
        if c.source == "ticket_body":
            source_text = tickets_by_id[c.ticket_id].body
        elif c.source == "escalation_notes":
            source_text = "\n".join(account.escalation_notes)
        else:
            raise AssertionError(f"Unknown source: {c.source}")

        assert c.quote in source_text, (
            f"Quote not verbatim in source! ticket_id={c.ticket_id} "
            f"source={c.source} quote={c.quote!r}"
        )


if __name__ == "__main__":
    from src.common.data_loader import (
        get_account_by_company,
        get_tickets_for_company,
        load_accounts,
    )

    accounts = load_accounts()
    # Find an account with escalation_notes to make the test meaningful.
    test_account = next((a for a in accounts if a.escalation_notes), accounts[0])
    tickets = get_tickets_for_company(test_account.company, window_days=None)

    candidates = extract_risk_candidates(tickets, test_account)
    print(f"Account: {test_account.company} ({len(tickets)} tickets, "
          f"{len(test_account.escalation_notes)} escalation notes)")
    print(f"Found {len(candidates)} risk candidates:\n")

    for c in candidates:
        print(f"  [{c.category.value}] (ticket={c.ticket_id or 'escalation_notes'})")
        print(f"    matched: {c.matched_pattern!r}")
        print(f"    quote:   {c.quote!r}\n")

    assert_all_quotes_verbatim(candidates, tickets, test_account)
    print("✓ All quotes verified verbatim in source text.")