"""
Thin wrapper around the Ollama Python client.

Centralizes: model selection, deterministic sampling params (temperature/seed),
JSON-mode enforcement, and retry-on-invalid-output — so Task 1 and Task 2 don't
each reimplement "call the model and hope it returns valid JSON."
"""

from __future__ import annotations

import json
import logging
from typing import Type, TypeVar

import ollama
from pydantic import BaseModel, ValidationError

from src.common.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_client = ollama.Client(host=settings.ollama_host)


class LLMGenerationError(RuntimeError):
    """Raised when the model fails to produce valid output after all retries."""


def generate_text(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> str:
    """Plain text generation, no schema enforcement. Used for free-form drafting."""
    response = _client.chat(
        model=model or settings.ollama_model,
        messages=(
            ([{"role": "system", "content": system}] if system else [])
            + [{"role": "user", "content": prompt}]
        ),
        options={
            "temperature": temperature if temperature is not None else settings.llm_temperature,
            "seed": settings.llm_seed,
        },
    )
    return response["message"]["content"].strip()


def generate_structured(
    prompt: str,
    schema: Type[T],
    system: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_retries: int = 3,
) -> T:
    """
    Generate output constrained to a Pydantic schema via Ollama's JSON mode,
    validate it, and retry with an error-correction hint if validation fails.

    This is the core reliability mechanism for small local models: rather than
    trusting the model to always emit valid JSON matching our schema, we
    validate every response and feed the validation error back in on retry.
    """
    schema_hint = json.dumps(schema.model_json_schema(), indent=2)
    full_system = (
        (system + "\n\n" if system else "")
        + "Respond with ONLY a single valid JSON object matching this schema. "
        + "No markdown fences, no commentary, no text outside the JSON object.\n\n"
        + f"JSON schema:\n{schema_hint}"
    )

    last_error: Exception | None = None
    current_prompt = prompt

    for attempt in range(1, max_retries + 1):
        response = _client.chat(
            model=model or settings.ollama_model,
            messages=[
                {"role": "system", "content": full_system},
                {"role": "user", "content": current_prompt},
            ],
            format="json",
            options={
                "temperature": temperature if temperature is not None else settings.llm_temperature,
                "seed": settings.llm_seed,
            },
        )
        raw = response["message"]["content"].strip()

        try:
            parsed = json.loads(raw)
            return schema.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            logger.warning(
                "generate_structured attempt %d/%d failed validation: %s",
                attempt, max_retries, e,
            )
            current_prompt = (
                f"{prompt}\n\n"
                f"Your previous response was invalid: {e}\n"
                f"Previous response was: {raw}\n"
                f"Fix it and respond again with ONLY the corrected JSON object."
            )

    raise LLMGenerationError(
        f"Failed to get valid {schema.__name__} after {max_retries} attempts. "
        f"Last error: {last_error}"
    )


if __name__ == "__main__":
    # Quick manual check: `python -m src.common.ollama_client`
    from pydantic import Field

    class _Ping(BaseModel):
        answer: str = Field(description="one word answer")

    print("Testing generate_text...")
    print(generate_text("Say hello in exactly one word."))

    print("\nTesting generate_structured...")
    result = _Ping.model_validate(
        generate_structured(
            "What is the capital of France? Answer in the 'answer' field.",
            schema=_Ping,
        )
    )
    print(result)