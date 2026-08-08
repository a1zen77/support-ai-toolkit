"""
Loads and joins the provided dataset (tickets.json, accounts.json).

Key design decision: tickets are joined to accounts on `company`, not
`account_id`. In the provided dataset, `ticket.account_id` essentially never
matches a real account_id in accounts.json (verified: 496/500 tickets have no
valid account_id match, and even the 4 "matches" are coincidental — wrong
company). `company` is a 100% reliable join key across all 500 tickets and
50 accounts. See docs/design_note.md for the full write-up.
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache

from src.common.config import settings
from src.common.schemas import Account, Ticket


@lru_cache(maxsize=1)
def load_tickets() -> list[Ticket]:
    raw = json.loads(settings.tickets_path.read_text())
    return [Ticket(**r) for r in raw]


@lru_cache(maxsize=1)
def load_accounts() -> list[Account]:
    raw = json.loads(settings.accounts_path.read_text())
    return [Account(**r) for r in raw]


@lru_cache(maxsize=1)
def _accounts_by_company() -> dict[str, Account]:
    return {a.company: a for a in load_accounts()}


def get_account_by_id(account_id: str) -> Account | None:
    for a in load_accounts():
        if a.account_id == account_id:
            return a
    return None


def get_account_by_company(company: str) -> Account | None:
    return _accounts_by_company().get(company)


def get_tickets_for_company(
    company: str,
    as_of: date | None = None,
    window_days: int | None = 90,
) -> list[Ticket]:
    """
    Tickets for a given company, optionally windowed to the last `window_days`
    relative to `as_of` (defaults to settings.as_of_date, which is the
    dataset's own max ticket date — see config.py for why real wall-clock
    "today" would be wrong here). Pass window_days=None for all-time.
    """
    matches = [t for t in load_tickets() if t.company == company]

    if window_days is None:
        return matches

    as_of = as_of or settings.as_of_date
    cutoff = as_of.toordinal() - window_days
    return [t for t in matches if t.created_at.date().toordinal() >= cutoff]


def get_tickets_for_account(
    account: Account,
    as_of: date | None = None,
    window_days: int = 90,
) -> list[Ticket]:
    """Convenience wrapper: resolve tickets via account.company, not account_id."""
    return get_tickets_for_company(account.company, as_of=as_of, window_days=window_days)


if __name__ == "__main__":
    # Quick manual check: `python -m src.common.data_loader`
    tickets = load_tickets()
    accounts = load_accounts()
    print(f"Loaded {len(tickets)} tickets, {len(accounts)} accounts")

    sample_account = accounts[0]
    windowed = get_tickets_for_account(sample_account)
    all_time = get_tickets_for_account(sample_account, window_days=None)
    print(
        f"Account {sample_account.account_id} ({sample_account.company}): "
        f"{len(windowed)} tickets in last 90d, {len(all_time)} all-time"
    )

    # Sanity check the company join covers everyone
    unmatched = [a.company for a in accounts if not get_tickets_for_company(a.company, window_days=None)]
    print(f"Accounts with zero tickets ever: {len(unmatched)} -> {unmatched}")