"""
Task 2 pipeline: assemble account + tickets -> extract risk candidates
(non-LLM) -> LLM synthesizes summary/talking-points and SELECTS risks by
index -> reconstitute final AccountBrief using verbatim quote text pulled
from the verified candidates, never from the LLM's own output.
"""

from __future__ import annotations

import logging

from src.common.data_loader import get_account_by_company, get_tickets_for_company
from src.common.ollama_client import generate_structured
from src.common.config import settings
from src.common.schemas import Account, AccountBrief, RiskFlag, Ticket
from src.task2_account_brief.prompts import (
    BRIEF_SYNTHESIS_SYSTEM,
    build_brief_synthesis_prompt,
)
from src.task2_account_brief.risk_signals import (
    assert_all_quotes_verbatim,
    extract_risk_candidates,
)
from src.task2_account_brief.schemas import BriefSynthesisOutput, RiskCandidate

logger = logging.getLogger(__name__)


def _resolve_selected_risks(
    output: BriefSynthesisOutput,
    candidates: list[RiskCandidate],
    account: Account,
) -> list[RiskFlag]:
    flags: list[RiskFlag] = []
    for selected in output.selected_risks:
        idx = selected.candidate_index
        if idx < 0 or idx >= len(candidates):
            logger.warning(
                "LLM selected out-of-range candidate_index=%d (valid range: 0-%d) "
                "for account=%s - dropping this risk rather than trusting it.",
                idx, len(candidates) - 1, account.company,
            )
            continue

        candidate = candidates[idx]
        flags.append(
            RiskFlag(
                ticket_id=candidate.ticket_id or account.account_id,
                quote=candidate.quote,  # verbatim, from the verified candidate - never from the LLM
                source=candidate.source,
                explanation=selected.explanation,
            )
        )
    return flags


def generate_account_brief(
    account_id: str | None = None,
    company: str | None = None,
    window_days: int | None = 90,
) -> AccountBrief:
    """
    Provide either account_id or company. Tickets are joined on `company`
    (see data_loader design decision - account_id is unreliable in this
    dataset), so if account_id is given, we resolve it to an Account first
    to get the company, then join on that.
    """
    if account_id:
        from src.common.data_loader import load_accounts
        account = next((a for a in load_accounts() if a.account_id == account_id), None)
        if account is None:
            raise ValueError(f"No account found with account_id={account_id!r}")
    elif company:
        account = get_account_by_company(company)
        if account is None:
            raise ValueError(f"No account found with company={company!r}")
    else:
        raise ValueError("Must provide either account_id or company")

    tickets = get_tickets_for_company(account.company, window_days=window_days)

    candidates = extract_risk_candidates(tickets, account)
    # Defense in depth: re-verify verbatim-ness right before this feeds an
    # LLM prompt, not just at extraction time.
    assert_all_quotes_verbatim(candidates, tickets, account)

    prompt = build_brief_synthesis_prompt(account, tickets, candidates)
    llm_output = generate_structured(
        prompt=prompt,
        schema=BriefSynthesisOutput,
        system=BRIEF_SYNTHESIS_SYSTEM,
    )

    risk_flags = _resolve_selected_risks(llm_output, candidates, account)

    return AccountBrief(
        account_id=account.account_id,
        company=account.company,
        as_of_date=settings.as_of_date,
        executive_summary=llm_output.executive_summary,
        risks_and_flags=risk_flags,
        talking_points=llm_output.talking_points,
        tickets_considered=len(tickets),
    )


if __name__ == "__main__":
    import json

    brief = generate_account_brief(company="Omni Consumer Products", window_days=None)
    print(json.dumps(brief.model_dump(), indent=2, default=str))