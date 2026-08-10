"""
Internal schemas for Task 2. RiskCandidate is produced entirely by
non-LLM keyword/pattern matching over verbatim ticket text — the LLM
never sees this stage as something it can edit the quote text of; it can
only select from and narrate around these pre-verified candidates.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RiskCategory(str, Enum):
    CHURN_INTENT = "Churn Intent"           # explicit cancel/switch/leave language
    ESCALATION = "Escalation"                # asked for manager, formal escalation
    REPEATED_ISSUE = "Repeated Issue"        # "again", "still not fixed", "third time"
    SLA_BREACH = "SLA Breach"                # missed deadline/response time language
    EXECUTIVE_ATTENTION = "Executive Attention"  # CEO/leadership involvement mentioned
    DISSATISFACTION = "Dissatisfaction"      # strong negative sentiment language
    COMPETITOR_MENTION = "Competitor Mention"  # evaluating alternatives


class RiskCandidate(BaseModel):
    ticket_id: str | None = None  # None if sourced from account-level escalation_notes
    quote: str = Field(..., description="Verbatim substring of the source text")
    source: str  # "ticket_body" or "escalation_notes"
    category: RiskCategory
    matched_pattern: str  # the literal keyword/phrase that triggered this match
    sentence_index: int  # position within the source text, for dedup/ordering


if __name__ == "__main__":
    # Sanity check: model constructs and serializes cleanly.
    rc = RiskCandidate(
        ticket_id="T-0001",
        quote="We are seriously considering moving to a competitor next quarter.",
        source="ticket_body",
        category=RiskCategory.CHURN_INTENT,
        matched_pattern="considering moving to a competitor",
        sentence_index=2,
    )
    print(rc.model_dump_json(indent=2))