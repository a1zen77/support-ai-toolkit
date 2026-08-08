"""
Deterministic responder-team routing. Kept rule-based rather than LLM-based:
routing decisions should be predictable and auditable, not subject to model
variance, even with temperature=0.
"""

from __future__ import annotations

# Category -> team, checked first for categories that always route the same
# way regardless of product.
_CATEGORY_TEAM_OVERRIDES: dict[str, str] = {
    "Billing": "Billing Team",
    "Onboarding": "Customer Success / Onboarding Team",
    "Feature Request": "Product Team",
}

# Product -> team for categories that need product-specific engineering
# knowledge (Bug, Performance, Data Loss, Integration, How-To).
_PRODUCT_TEAM: dict[str, str] = {
    "SecureVault": "Security & Access Tier-2 Support",
    "DataBridge Pro": "Data Platform Tier-2 Support",
    "AnalyticsHub": "Analytics Tier-2 Support",
    "CloudSync": "Sync/Infra Tier-2 Support",
    "WorkflowEngine": "Automation Tier-2 Support",
}

_DEFAULT_TEAM = "Tier-1 Support"


def determine_responder_team(
    product: str | None,
    category: str,
    urgency: str,
) -> str:
    """
    Routing logic:
      1. Billing / Onboarding / Feature Request always go to their fixed team,
         regardless of product - these categories aren't product-engineering issues.
      2. How-To with no urgency pressure stays with Tier-1 (no need to escalate
         a question to Tier-2 engineering).
      3. Everything else (Bug, Performance, Data Loss, Integration, and How-To
         that's P1/P2) routes to the product-specific Tier-2 team.
      4. P1 tickets get an explicit escalation flag appended, regardless of team.
    """
    if category in _CATEGORY_TEAM_OVERRIDES:
        team = _CATEGORY_TEAM_OVERRIDES[category]
    elif category == "How-To" and urgency not in ("P1", "P2"):
        team = _DEFAULT_TEAM
    elif product and product in _PRODUCT_TEAM:
        team = _PRODUCT_TEAM[product]
    else:
        team = _DEFAULT_TEAM

    if urgency == "P1":
        team += " (P1 - immediate escalation required)"

    return team


if __name__ == "__main__":
    # Quick manual check: `python -m src.task1_triage.routing`
    cases = [
        ("SecureVault", "Bug", "P1"),
        ("SecureVault", "Bug", "P3"),
        ("DataBridge Pro", "Data Loss", "P1"),
        (None, "Billing", "P3"),
        ("AnalyticsHub", "How-To", "P4"),
        ("AnalyticsHub", "How-To", "P2"),
        ("CloudSync", "Feature Request", "P4"),
    ]
    for product, category, urgency in cases:
        team = determine_responder_team(product, category, urgency)
        print(f"{product} / {category} / {urgency} -> {team}")