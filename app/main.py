"""
FastAPI app exposing the triage pipeline as a REST endpoint.

Run with: uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from src.common.ollama_client import LLMGenerationError
from src.common.schemas import TicketInput, TriageResult
from src.task1_triage.pipeline import triage_ticket

from src.common.schemas import AccountBrief
from src.task2_account_brief.pipeline import generate_account_brief

app = FastAPI(
    title="Support Triage API",
    description="Classifies, routes, and drafts a first response for an incoming support ticket.",
    version="1.0.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/triage", response_model=TriageResult)
def triage(ticket: TicketInput) -> TriageResult:
    try:
        return triage_ticket(ticket)
    except LLMGenerationError as e:
        raise HTTPException(status_code=502, detail=f"LLM failed to produce valid output: {e}")
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

from pydantic import BaseModel

from src.task1_triage.pipeline import triage_raw_text


class RawTicketInput(BaseModel):
    text: str


@app.post("/triage/raw", response_model=TriageResult)
def triage_raw(payload: RawTicketInput) -> TriageResult:
    try:
        return triage_raw_text(payload.text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except LLMGenerationError as e:
        raise HTTPException(status_code=502, detail=f"LLM failed to produce valid output: {e}")

## TASK 2


class AccountBriefRequest(BaseModel):
    account_id: str | None = None
    company: str | None = None
    window_days: int | None = 90


@app.post("/account-brief", response_model=AccountBrief)
def account_brief(payload: AccountBriefRequest) -> AccountBrief:
    if not payload.account_id and not payload.company:
        raise HTTPException(
            status_code=422,
            detail="Must provide either account_id or company",
        )
    try:
        return generate_account_brief(
            account_id=payload.account_id,
            company=payload.company,
            window_days=payload.window_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMGenerationError as e:
        raise HTTPException(status_code=502, detail=f"LLM failed to produce valid output: {e}")