"""Provider-agnostic LLM client. Switch providers via LLM_PROVIDER in .env,
or pass `provider=` explicitly to mix providers per call (e.g. Groq for
decomposition, Claude for generation)."""

from __future__ import annotations

import logging
from typing import Literal

from tenacity import before_sleep_log, retry, retry_if_exception, stop_after_attempt, wait_exponential

from src import config

logger = logging.getLogger(__name__)

Provider = Literal["groq", "claude"]


def _is_transient(exc: BaseException) -> bool:
    """Retries rate limits, server errors, timeouts, and connection issues —
    both the Groq and Anthropic SDKs name these consistently, so matching on
    the exception class name avoids eagerly importing either library just
    for its exception types. Auth/bad-request errors are deliberately not
    retried — they won't succeed on a second attempt."""
    name = type(exc).__name__
    return any(kind in name for kind in ("RateLimit", "APIConnection", "APITimeout", "InternalServerError", "ServiceUnavailable"))


_llm_retry = retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class LLMClient:
    def __init__(self, provider: Provider | None = None):
        self.provider: Provider = provider or config.LLM_PROVIDER  # type: ignore[assignment]
        if self.provider not in ("groq", "claude"):
            raise ValueError(f"Unknown LLM_PROVIDER: {self.provider!r} (expected 'groq' or 'claude')")

    @_llm_retry
    def complete(self, prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
        """Send a single-turn prompt and return the model's text response."""
        logger.debug("LLM call (%s): %d char prompt", self.provider, len(prompt))
        if self.provider == "groq":
            return self._complete_groq(prompt, system, temperature)
        return self._complete_claude(prompt, system, temperature)

    def _complete_groq(self, prompt: str, system: str | None, temperature: float) -> str:
        from groq import Groq

        client = Groq(api_key=config.require(config.GROQ_API_KEY, "GROQ_API_KEY"))
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    def _complete_claude(self, prompt: str, system: str | None, temperature: float) -> str:
        from anthropic import Anthropic

        client = Anthropic(api_key=config.require(config.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=1024,
            temperature=temperature,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


def test_connection(provider: Provider, api_key: str, model: str) -> str:
    """Settings screen's "Test Connection" button: runs a minimal live call
    against a *candidate* key/model the user just typed in, without touching
    the app's saved config (LLMClient always reads from config.* globals, so
    testing an unsaved value needs its own path). Returns the model's reply
    on success; raises on failure — the caller translates that into a
    user-facing message."""
    if provider == "groq":
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            temperature=0,
        )
        return response.choices[0].message.content or ""

    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=16,
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
    )
    return "".join(block.text for block in response.content if block.type == "text")
