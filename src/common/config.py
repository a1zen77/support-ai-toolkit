"""
Central configuration for the Support & TAM AI Toolkit.

Loads values from `.env` (falling back to sensible defaults) and exposes them
as a single importable `settings` object, so every module reads config the
same way instead of scattering `os.getenv` calls around the codebase.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root, wherever this module is imported from.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


def _get_path(name: str, default: str) -> Path:
    val = os.getenv(name, default)
    p = Path(val)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    return p


def _get_date(name: str, default: str) -> date:
    val = os.getenv(name, default)
    return date.fromisoformat(val)


@dataclass(frozen=True)
class Settings:
    # Ollama
    ollama_host: str
    ollama_model: str
    ollama_judge_model: str

    # Embeddings
    embedding_model: str

    # Data paths
    project_root: Path
    tickets_path: Path
    accounts_path: Path
    kb_dir: Path

    # Determinism
    llm_temperature: float
    llm_seed: int

    # As-of date for "last 90 days" windows (Task 2)
    as_of_date: date

    # API server
    api_host: str
    api_port: int

    log_level: str


def load_settings() -> Settings:
    """Build a Settings object from environment variables (populated from .env)."""
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
    return Settings(
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        ollama_model=ollama_model,
        ollama_judge_model=os.getenv("OLLAMA_JUDGE_MODEL", ollama_model),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        project_root=_PROJECT_ROOT,
        tickets_path=_get_path("TICKETS_PATH", "data/tickets.json"),
        accounts_path=_get_path("ACCOUNTS_PATH", "data/accounts.json"),
        kb_dir=_get_path("KB_DIR", "knowledge_base"),
        llm_temperature=_get_float("LLM_TEMPERATURE", 0.0),
        llm_seed=_get_int("LLM_SEED", 42),
        as_of_date=_get_date("AS_OF_DATE", "2026-05-22"),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=_get_int("API_PORT", 8000),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


# Single shared instance — import this everywhere instead of calling load_settings().
settings = load_settings()


if __name__ == "__main__":
    # Quick manual check: `python -m src.common.config` from the project root.
    from pprint import pprint

    pprint(settings)