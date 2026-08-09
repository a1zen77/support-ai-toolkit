"""
Prompts for the triage pipeline, versioned explicitly so changes are
traceable (see PROMPT_CHANGELOG below). Task 3's eval harness pins a prompt
version per run so regressions are attributable to a specific prompt edit,
not silently absorbed.
"""

from __future__ import annotations

# --- Product -> valid product_area values, derived from the dataset itself ---
PRODUCT_AREAS: dict[str, list[str]] = {
    "DataBridge Pro": ["API", "Connectors", "Data Ingestion", "Pipeline Monitoring", "Schema Management"],
    "AnalyticsHub": ["Alerts", "Dashboard", "Data Sources", "Exports", "Reports"],
    "CloudSync": ["Bandwidth Limits", "Conflict Resolution", "File Sync", "Integrations", "Permissions"],
    "SecureVault": ["Audit Logs", "Authentication", "Encryption", "Key Management", "SSO"],
    "WorkflowEngine": ["Actions", "Error Handling", "Scheduling", "Templates", "Triggers"],
}

CATEGORIES = [
    "Bug", "Feature Request", "How-To", "Performance",
    "Billing", "Integration", "Onboarding", "Data Loss",
]

URGENCY_GUIDANCE = """
P1 - Critical: production down, data loss in progress, security breach, or
     a workflow-blocking issue affecting many users right now.
P2 - High: major feature broken or badly degraded for one customer/team,
     no workaround, but not full outage.
P3 - Medium: a real problem with a workaround available, or affects a
     single user/edge case, or a How-To/config question blocking progress.
P4 - Low: cosmetic issues, feature requests, general questions with no
     urgency, no one currently blocked.
""".strip()

# ---------------------------------------------------------------------------
# CLASSIFY_PROMPT
# v1 - 2026-08 - initial version
# v2 - 2026-08 - explicit instruction to always commit to one product_area
#      from the valid list, even under ambiguity (was returning "" on
#      tickets that don't explicitly name a product, e.g. generic "billing
#      dashboard" wording) - express uncertainty in reasoning text instead
# ---------------------------------------------------------------------------
CLASSIFY_PROMPT_VERSION = "classify_v2"

CLASSIFY_SYSTEM = f"""
You are a support ticket triage assistant for a company with five products:
DataBridge Pro, CloudSync, AnalyticsHub, SecureVault, WorkflowEngine.

Valid product areas per product:
{PRODUCT_AREAS}

Valid issue categories: {CATEGORIES}

Urgency tiers:
{URGENCY_GUIDANCE}

Read the ticket and classify it. Give brief, concrete reasoning (1-2 sentences)
for both category and urgency - reference specific words or phrases from the
ticket, don't just restate the label.

IMPORTANT: product_area is REQUIRED and must always be exactly one value from
the valid list for whichever product you choose - never leave it blank. Even
if the ticket doesn't explicitly name a product or area, infer the single
best match from context (e.g. a "dashboard" complaint maps to AnalyticsHub's
"Dashboard" area even if the ticket never says "AnalyticsHub"). If you are
genuinely uncertain between two options, pick the more likely one and note
the ambiguity in category_reasoning - do not leave product_area empty.
""".strip()


def build_classify_prompt(subject: str, body: str) -> str:
    return f"Ticket subject: {subject}\n\nTicket body:\n{body}"


# ---------------------------------------------------------------------------
# DRAFT_RESPONSE_PROMPT
# v1 - 2026-08 - initial version
# ---------------------------------------------------------------------------
DRAFT_RESPONSE_PROMPT_VERSION = "draft_response_v1"

DRAFT_RESPONSE_SYSTEM = """
You are drafting a first-response message for a support agent to send to a
customer. Tone: professional, empathetic, concise. Do not promise specific
timelines you don't know. If knowledge-base context is provided, ground your
suggested next steps in it and reference the relevant steps naturally -
don't fabricate steps that aren't in the provided context. If no KB context
is provided, acknowledge the issue and explain what the agent will do next
(investigate / escalate) without inventing a resolution.
""".strip()


def build_draft_response_prompt(
    subject: str,
    body: str,
    kb_context: str | None,
) -> str:
    kb_block = (
        f"\n\nRelevant knowledge-base context:\n{kb_context}"
        if kb_context
        else "\n\nNo matching knowledge-base article was found."
    )
    return (
        f"Ticket subject: {subject}\n\nTicket body:\n{body}{kb_block}\n\n"
        f"Write the first-response message now (just the message, no preamble)."
    )


# ---------------------------------------------------------------------------
# Changelog
# ---------------------------------------------------------------------------
PROMPT_CHANGELOG = """
2026-08 - classify_v1, draft_response_v1: initial versions.
2026-08 - classify_v2: added explicit instruction requiring product_area to
          always be a concrete, non-blank value from the valid list, even
          under ambiguity. Fixes ClassificationOutput validation failures on
          tickets that don't explicitly name a product (e.g. generic
          "billing dashboard" wording resolved to product_area='').
""".strip()