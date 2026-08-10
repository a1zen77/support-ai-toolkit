"""
Prompts for Task 2 (Account Health Summariser), versioned per prompts.py
convention from Task 1. The LLM never generates quote text - it only
selects from a pre-verified candidate list (by index) and writes its own
explanation/summary/talking-point prose around them.
"""

from __future__ import annotations

from src.common.schemas import Account, Ticket
from src.task2_account_brief.schemas import RiskCandidate

# ---------------------------------------------------------------------------
# BRIEF_SYNTHESIS_PROMPT
# v1 - 2026-08 - initial version. Risk candidates are pre-extracted
#      non-LLM (see risk_signals.py); LLM selects by index + explains,
#      never generates quote text. This is enforced structurally by
#      BriefSynthesisOutput having no quote field at all.
# ---------------------------------------------------------------------------
BRIEF_SYNTHESIS_PROMPT_VERSION = "brief_synthesis_v1"

BRIEF_SYNTHESIS_SYSTEM = """
You are writing an internal account health brief for a Technical Account
Manager (TAM), based on ticket history and pre-verified risk signals for
one customer account.

You will be given:
1. Account facts (health status, usage trend, plan tier, ARR, NPS, renewal
   date, seat utilization).
2. A summary of recent tickets (counts by category/urgency, not full text).
3. A numbered list of pre-verified risk candidates - each is a VERBATIM
   quote already confirmed to exist in the account's ticket or escalation
   data, tagged with a risk category.

Your job has three parts:

EXECUTIVE SUMMARY (2-4 sentences): Summarize overall account health using
the account facts and ticket patterns provided. Be concrete - reference
actual numbers (ticket counts, urgency mix, usage trend) rather than vague
language like "some issues were noted."

RISK SELECTION: Review the numbered risk candidates. Select the ones that
are genuinely significant for this account's health (you do not have to
select all of them - omit weak or redundant signals). For each one you
select, provide the candidate_index exactly as given and a 1-2 sentence
explanation of why it matters, IN YOUR OWN WORDS. Do NOT quote or restate
the candidate text itself in your explanation - just explain its
significance. You may select zero candidates if none are genuinely
significant, or if the candidate list is empty.

CRITICAL: You may ONLY select candidate_index values that appear in the
numbered list provided. Never invent a candidate_index. Never describe a
risk that isn't backed by one of the provided candidates.

TALKING POINTS (2-5 bullet points): Forward-looking discussion points for
the TAM's next conversation with this customer - e.g. renewal timing,
usage/seat mismatches, unresolved technical issues, expansion
opportunities. Base these ONLY on the account facts and ticket summary
provided - do not invent product details, dates, or commitments not
present in the input.
""".strip()


def _format_account_facts(account: Account) -> str:
    seat_utilization = (
        f"{account.seats_active}/{account.seats_licensed} "
        f"({account.seats_active / account.seats_licensed:.0%})"
        if account.seats_licensed
        else "unknown"
    )
    return (
        f"Company: {account.company}\n"
        f"Plan tier: {account.plan_tier}\n"
        f"ARR: ${account.arr_usd:,}\n"
        f"Health status: {account.health_status}\n"
        f"Usage trend: {account.usage_trend}\n"
        f"Seat utilization: {seat_utilization}\n"
        f"Open tickets: {account.open_tickets}\n"
        f"P1 tickets (last 30d): {account.p1_tickets_last_30d}\n"
        f"NPS score: {account.nps_score if account.nps_score is not None else 'not available'}\n"
        f"Renewal date: {account.renewal_date}\n"
        f"Last QBR date: {account.last_qbr_date}\n"
        f"Region: {account.region}\n"
        f"Industry: {account.industry}"
    )


def _format_ticket_summary(tickets: list[Ticket]) -> str:
    if not tickets:
        return "No tickets in the considered window."

    by_category: dict[str, int] = {}
    by_urgency: dict[str, int] = {}
    for t in tickets:
        by_category[t.category] = by_category.get(t.category, 0) + 1
        by_urgency[t.urgency] = by_urgency.get(t.urgency, 0) + 1

    cat_line = ", ".join(f"{k}: {v}" for k, v in sorted(by_category.items(), key=lambda x: -x[1]))
    urg_line = ", ".join(f"{k}: {v}" for k, v in sorted(by_urgency.items(), key=lambda x: -x[1]))

    return (
        f"Total tickets considered: {len(tickets)}\n"
        f"By category: {cat_line}\n"
        f"By urgency: {urg_line}"
    )


def _format_risk_candidates(candidates: list[RiskCandidate]) -> str:
    if not candidates:
        return "No risk candidates were detected for this account."

    lines = []
    for i, c in enumerate(candidates):
        source_label = c.ticket_id if c.ticket_id else "escalation_notes"
        lines.append(
            f'[{i}] category={c.category.value} source={source_label}\n'
            f'    quote: "{c.quote}"'
        )
    return "\n".join(lines)


def build_brief_synthesis_prompt(
    account: Account,
    tickets: list[Ticket],
    candidates: list[RiskCandidate],
) -> str:
    return (
        f"=== ACCOUNT FACTS ===\n{_format_account_facts(account)}\n\n"
        f"=== TICKET SUMMARY ({len(tickets)} tickets considered) ===\n"
        f"{_format_ticket_summary(tickets)}\n\n"
        f"=== RISK CANDIDATES ===\n{_format_risk_candidates(candidates)}\n\n"
        f"Write the account health brief now."
    )


PROMPT_CHANGELOG = """
2026-08 - brief_synthesis_v1: initial version. Risk candidates are
          pre-extracted non-LLM and passed in as a numbered, verbatim list;
          LLM output schema (BriefSynthesisOutput) has no quote field, so
          quote fabrication is structurally impossible, not just
          instructed against.
""".strip()