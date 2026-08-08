"""
Shared Pydantic models for the Support & TAM AI Toolkit.

Two kinds of models live here:
  1. Dataset models (Ticket, Account) — mirror the provided data files exactly,
     used when loading data/tickets.json and data/accounts.json.
  2. Task I/O models (TicketInput, TriageResult, etc.) — define what Task 1 and
     Task 2 accept and return, independent of the raw dataset shape.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums (constrain LLM output to known-valid values)
# ---------------------------------------------------------------------------

class IssueCategory(str, Enum):
    BUG = "Bug"
    FEATURE_REQUEST = "Feature Request"
    HOW_TO = "How-To"
    PERFORMANCE = "Performance"
    BILLING = "Billing"
    INTEGRATION = "Integration"
    ONBOARDING = "Onboarding"
    DATA_LOSS = "Data Loss"


class Urgency(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class Product(str, Enum):
    DATABRIDGE_PRO = "DataBridge Pro"
    CLOUDSYNC = "CloudSync"
    ANALYTICSHUB = "AnalyticsHub"
    SECUREVAULT = "SecureVault"
    WORKFLOWENGINE = "WorkflowEngine"


# ---------------------------------------------------------------------------
# Dataset models — mirror data/tickets.json and data/accounts.json
# ---------------------------------------------------------------------------

class Ticket(BaseModel):
    ticket_id: str
    account_id: str
    company: str
    subject: str
    body: str
    product: str
    product_area: str
    category: str
    urgency: str
    status: str
    plan_tier: str
    assigned_agent: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)
    channel: str
    satisfaction_score: Optional[int] = None


class PrimaryContact(BaseModel):
    name: str
    title: str


class Account(BaseModel):
    account_id: str
    company: str
    tam: str
    plan_tier: str
    arr_usd: int
    seats_licensed: int
    seats_active: int
    products: list[str] = Field(default_factory=list)
    health_status: str
    usage_trend: str
    open_tickets: int
    p1_tickets_last_30d: int
    renewal_date: date
    last_qbr_date: date
    escalation_notes: list[str] = Field(default_factory=list)
    nps_score: Optional[int] = None
    primary_contact: PrimaryContact
    integrations_active: list[str] = Field(default_factory=list)
    region: str
    industry: str


# ---------------------------------------------------------------------------
# Task 1 — Triage: input / output
# ---------------------------------------------------------------------------

class TicketInput(BaseModel):
    """
    What a caller submits to the triage pipeline. Deliberately minimal — the
    brief requires triage to work from raw free-text, not from the dataset's
    pre-existing ground-truth labels.
    """
    subject: str
    body: str
    # Optional context a real intake form might have; triage should still
    # work correctly if these are absent.
    company: Optional[str] = None
    channel: Optional[str] = None


class KBMatch(BaseModel):
    doc_path: str
    doc_title: str
    matched_reason: str  # e.g. "exact error code match: AUTH_TOKEN_EXPIRED"
    relevance_score: float


class TriageResult(BaseModel):
    product: Optional[str] = None
    product_area: str
    category: IssueCategory
    category_reasoning: str
    urgency: Urgency
    urgency_reasoning: str
    kb_matches: list[KBMatch] = Field(default_factory=list)
    recommended_team: str
    draft_response: str


# ---------------------------------------------------------------------------
# Task 2 — Account brief: output
# ---------------------------------------------------------------------------

class RiskFlag(BaseModel):
    ticket_id: str
    quote: str  # must be a verbatim substring of the ticket body or escalation_notes
    source: str  # "ticket_body" or "escalation_notes"
    explanation: str


class AccountBrief(BaseModel):
    account_id: str
    company: str
    as_of_date: date
    executive_summary: str
    risks_and_flags: list[RiskFlag] = Field(default_factory=list)
    talking_points: list[str] = Field(default_factory=list)
    tickets_considered: int