"""Second LLM pass over generated test cases: audits whether each is
grounded in the source requirement, detects which of the 7 categories have
zero cases (a coverage gap), and re-runs generation scoped to just the
missing categories."""

from __future__ import annotations

import json
import re

from src.generation.generator import generate_test_cases_for_categories
from src.generation.llm_client import LLMClient
from src.generation.prompts import AUDIT_SYSTEM_PROMPT, build_audit_user_prompt
from src.models.schemas import Category, TestCase
from src.retrieval.retriever import RetrievedContext

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _summarize(tc: TestCase) -> str:
    category = tc.category.value if tc.category else "Uncategorized"
    steps = "; ".join(tc.steps)
    return f"[{category}] {tc.title} — Steps: {steps} — Expected: {tc.expected_result}"


def parse_audit_results(llm_response: str, test_cases: list[TestCase]) -> list[TestCase]:
    """Applies the LLM's per-case grounded verdicts, in order, onto the given
    test cases. Pure/deterministic — testable without a live API."""
    text = _FENCE_RE.sub("", llm_response.strip()).strip()
    data = json.loads(text)
    if not isinstance(data, list) or len(data) != len(test_cases):
        got = len(data) if isinstance(data, list) else type(data).__name__
        raise ValueError(f"Expected {len(test_cases)} audit results, got {got}")

    return [tc.model_copy(update={"grounded": bool(result.get("grounded", False))}) for tc, result in zip(test_cases, data)]


def audit_grounding(
    test_cases: list[TestCase], requirement_text: str, provider: str | None = None
) -> list[TestCase]:
    if not test_cases:
        return []
    prompt = build_audit_user_prompt(requirement_text, [_summarize(tc) for tc in test_cases])
    client = LLMClient(provider=provider)
    response = client.complete(prompt=prompt, system=AUDIT_SYSTEM_PROMPT, temperature=0.0)
    return parse_audit_results(response, test_cases)


def find_gaps(test_cases: list[TestCase]) -> list[Category]:
    """Pure/deterministic: which of the 7 categories have zero test cases
    among the given set."""
    present = {tc.category for tc in test_cases if tc.category is not None}
    return [c for c in Category if c not in present]


def regenerate_gaps(
    condition_text: str,
    condition_id: str,
    context: RetrievedContext,
    missing_categories: list[Category],
    trace: str | None = None,
    module: str | None = None,
    provider: str | None = None,
    existing_ids: set[str] | None = None,
    id_prefix: str | None = None,
) -> list[TestCase]:
    """Re-runs generation scoped to only the missing categories. May still
    return fewer cases than requested — a category can legitimately not
    apply to a given condition (see prompts.build_targeted_generation_user_prompt)."""
    if not missing_categories:
        return []
    return generate_test_cases_for_categories(
        condition_text,
        condition_id,
        context,
        categories=[c.value for c in missing_categories],
        trace=trace,
        module=module,
        provider=provider,
        existing_ids=existing_ids,
        id_prefix=id_prefix,
    )
