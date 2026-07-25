"""Loads environment variables and exposes them as typed constants."""

import os
from pathlib import Path

from dotenv import load_dotenv, set_key

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- LLM provider ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

# --- Jira ---
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
# Fallback project to upload generated "Test Case" issues into when a run's
# source isn't a Jira ticket (a doc-sourced run has no project to derive this
# from). Jira-ticket-sourced runs upload into that ticket's own project instead.
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "")

# --- Optional rerank providers ---
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")

# --- Local storage ---
CHROMA_DB_DIR = str(PROJECT_ROOT / os.getenv("CHROMA_DB_DIR", "chroma_db"))


def require(value: str, name: str) -> str:
    """Raise a clear error if a required config value is missing."""
    if not value:
        raise RuntimeError(f"{name} is not set. Add it to your .env file (see .env.example).")
    return value


def update(**kwargs: str | None) -> None:
    """Persists the given values to .env and updates this module's own
    globals immediately — every other module reads these via `config.NAME`
    attribute access (never `from config import NAME`), so the new value
    takes effect for the next call with no restart needed.

    None/empty values are skipped, so a blank field in a settings form
    doesn't wipe an already-saved secret. Keys must already exist as a
    module-level constant above (typo-guarded)."""
    for key, value in kwargs.items():
        if not value:
            continue
        if key not in globals():
            raise ValueError(f"Unknown config key: {key!r}")
        if key == "LLM_PROVIDER":
            value = value.lower()
        globals()[key] = value
        set_key(str(ENV_PATH), key, value)
