"""
The core triage pipeline: classify -> retrieve KB context -> route -> draft.
This is the function Task 1's FastAPI endpoint will call directly.
"""

from __future__ import annotations

from src.common.ollama_client import generate_structured, generate_text
from src.common.schemas import TicketInput, TriageResult
from src.kb_retrieval.retriever import retrieve_with_context
from src.task1_triage.prompts import (
    CLASSIFY_SYSTEM,
    DRAFT_RESPONSE_SYSTEM,
    build_classify_prompt,
    build_draft_response_prompt,
)
from src.task1_triage.routing import determine_responder_team
from src.task1_triage.schemas import ClassificationOutput


def triage_ticket(ticket: TicketInput) -> TriageResult:
    # 1. Classify (product, area, category, urgency + reasoning)
    classification = generate_structured(
        prompt=build_classify_prompt(ticket.subject, ticket.body),
        schema=ClassificationOutput,
        system=CLASSIFY_SYSTEM,
    )

    # 2. KB retrieval - query on the raw ticket text, not the classification
    # label, since the ticket's own wording is more specific than a category name.
    query_text = f"{ticket.subject}\n{ticket.body}"
    kb_results = retrieve_with_context(query_text, top_k=2)
    kb_matches = [m for m, _ in kb_results]

    # Use a stricter threshold for what actually grounds the draft than what
    # we're willing to surface as a "possible match" to the agent. A 0.38
    # semantic match is worth showing the agent as a maybe; it's not solid
    # enough to let the LLM build specific customer-facing instructions on.
    MIN_SCORE_FOR_DRAFT_GROUNDING = 0.5
    strong_results = [
        (m, text) for m, text in kb_results if m.relevance_score >= MIN_SCORE_FOR_DRAFT_GROUNDING
    ]
    kb_context = (
        "\n\n---\n\n".join(text for _, text in strong_results) if strong_results else None
    )

    # 3. Routing - deterministic, not LLM-based (see routing.py)
    team = determine_responder_team(
        product=classification.product.value,
        category=classification.category.value,
        urgency=classification.urgency.value,
    )

    # 4. Draft first-response, grounded in KB context when available
    draft = generate_text(
        prompt=build_draft_response_prompt(ticket.subject, ticket.body, kb_context),
        system=DRAFT_RESPONSE_SYSTEM,
    )

    return TriageResult(
        product=classification.product.value,
        product_area=classification.product_area,
        category=classification.category,
        category_reasoning=classification.category_reasoning,
        urgency=classification.urgency,
        urgency_reasoning=classification.urgency_reasoning,
        kb_matches=kb_matches,
        recommended_team=team,
        draft_response=draft,
    )


if __name__ == "__main__":
    # Quick manual check: `python -m src.task1_triage.pipeline`
    import json

    test_ticket = TicketInput(
        subject="SSO login failing for all users",
        body=(
            "Since this morning none of our users can log in via SSO. "
            "We're seeing AUTH_TOKEN_EXPIRED errors in the browser console. "
            "This is blocking our entire team from accessing the platform."
        ),
    )
    result = triage_ticket(test_ticket)
    print(json.dumps(result.model_dump(), indent=2, default=str))