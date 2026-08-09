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