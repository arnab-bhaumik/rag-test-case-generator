"""Breaks a requirement into atomic testable conditions via the LLM.

Split into three pieces on purpose: build_user_prompt() and parse_conditions()
are pure/deterministic and unit-testable without hitting a live API; decompose()
is the thin wrapper that actually calls the LLM."""

from __future__ import annotations

import json
import re

from src.generation.llm_client import LLMClient
from src.models.schemas import Condition

SYSTEM_PROMPT = """You are a meticulous QA analyst decomposing a software requirement into atomic, independently testable conditions.

Rules:
- Each condition must describe exactly ONE testable behavior — never combine multiple checks into one condition.
- Conditions must be concrete and verifiable, not vague restatements of the requirement.
- If the requirement lists acceptance criteria, decompose each into one or more conditions and reference which AC it came from (e.g. "AC-2"); use null if there's no explicit AC reference.
- Do not invent behavior that is not stated or clearly implied by the requirement text.
- Return ONLY a valid JSON array of objects with keys "text" and "ac_ref" (string or null). No prose, no markdown code fences."""

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def build_user_prompt(requirement_text: str, scope: str | None = None) -> str:
    scope = (scope or "").strip()
    scope_instruction = (
        f"Focus ONLY on generating conditions related to this scope:\n{scope}\n\n"
        "Use the rest of the requirement text below purely as supporting context to understand that scope — "
        "do not generate conditions for behavior outside it, even if it looks testable on its own.\n\n"
        if scope
        else ""
    )
    return (
        f"{scope_instruction}Requirement:\n\n{requirement_text.strip()}\n\n"
        "Decompose this into atomic testable conditions as a JSON array."
    )


def parse_conditions(llm_response: str, requirement_id: str) -> list[Condition]:
    """Parses the LLM's JSON array response into Condition objects. Strips
    markdown code fences some models wrap JSON output in."""
    text = _FENCE_RE.sub("", llm_response.strip()).strip()
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of conditions")

    conditions = []
    for i, item in enumerate(data):
        text_value = str(item["text"]).strip()
        if not text_value:
            continue
        conditions.append(
            Condition(
                id=f"{requirement_id}::C{i + 1}",
                requirement_id=requirement_id,
                text=text_value,
                ac_ref=item.get("ac_ref") or None,
                order=i,
            )
        )
    return conditions


def decompose(requirement_text: str, requirement_id: str, provider: str | None = None, scope: str | None = None) -> list[Condition]:
    client = LLMClient(provider=provider)
    response = client.complete(
        prompt=build_user_prompt(requirement_text, scope=scope),
        system=SYSTEM_PROMPT,
        temperature=0.1,
    )
    return parse_conditions(response, requirement_id)
