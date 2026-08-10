"""
Shared pytest fixtures for the eval harness. Loads the dataset once per
test session - tests should treat these as read-only.
"""

from __future__ import annotations

import pytest

from src.common.data_loader import get_tickets_for_company, load_accounts, load_tickets
from src.common.schemas import Account, Ticket


@pytest.fixture(scope="session")
def all_accounts() -> list[Account]:
    return load_accounts()


@pytest.fixture(scope="session")
def all_tickets() -> list[Ticket]:
    return load_tickets()


@pytest.fixture(scope="session")
def account_ticket_pairs(all_accounts: list[Account]) -> list[tuple[Account, list[Ticket]]]:
    """(account, all-time tickets for that account) for every account in the dataset."""
    return [
        (account, get_tickets_for_company(account.company, window_days=None))
        for account in all_accounts
    ]