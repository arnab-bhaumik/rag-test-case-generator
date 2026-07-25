"""Generates test cases for a single condition + retrieved context, via the
LLM. Split the same way decomposer.py is: parse_test_cases() is pure/
deterministic and unit-testable without a live API; the generate_* functions
are the thin wrappers that actually call the LLM."""

from __future__ import annotations

import json
import re

from src.generation.llm_client import LLMClient
from src.generation.prompts import (
    ALL_CATEGORIES,
    GENERATION_SYSTEM_PROMPT,
    build_generation_user_prompt,
    build_targeted_generation_user_prompt,
)
from src.models.schemas import Priority, TestCase
from src.retrieval.retriever import RetrievedContext
from src.vectorstore.test_cases_store import next_sequence_ids

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_VALID_CATEGORIES = set(ALL_CATEGORIES)
_VALID_PRIORITIES = {p.value for p in Priority}


def parse_test_cases(
    llm_response: str,
    condition_id: str,
    trace: str | None = None,
    module: str | None = None,
    existing_ids: set[str] | None = None,
    id_prefix: str | None = None,
) -> list[TestCase]:
    """Parses the LLM's JSON array response into TestCase objects. Cases
    generated here start as `grounded=False` — coverage_auditor.py sets the
    real value after auditing; a case that's never audited should not read
    as trusted by default.

    IDs default to TC_{MODULE}_### — sequential per module, continuing from
    whatever's already used in the library — unless the user supplied their
    own `id_prefix` on the Generate screen (e.g. "DEMND002_Reg_TC_"), which
    is used verbatim instead. `existing_ids` covers cases already minted
    earlier in the same run (initial generation, gap-fill, single-case
    regenerate can all call this multiple times for one run) that haven't
    been approved into the library yet, so numbering never collides with its
    own not-yet-approved siblings — see test_cases_store.next_sequence_ids()."""
    text = _FENCE_RE.sub("", llm_response.strip()).strip()
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of test cases")

    valid: list[tuple[dict, str, str]] = []
    for item in data:
        category = item.get("category")
        if category not in _VALID_CATEGORIES:
            continue  # skip cases the model mis-categorized rather than fail the whole batch
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        valid.append((item, category, title))

    ids = next_sequence_ids(module, len(valid), extra_existing_ids=existing_ids, custom_prefix=id_prefix)

    cases = []
    for (item, category, title), case_id in zip(valid, ids):
        priority = item.get("priority") if item.get("priority") in _VALID_PRIORITIES else "Medium"
        cases.append(
            TestCase(
                id=case_id,
                title=title,
                description=str(item.get("description", "")).strip(),
                preconditions=str(item.get("preconditions", "")).strip(),
                steps=[str(s).strip() for s in item.get("steps", []) if str(s).strip()],
                expected_result=str(item.get("expected_result", "")).strip(),
                category=category,
                priority=priority,
                module=module,
                source="generated",
                trace=trace,
                grounded=False,
                condition_id=condition_id,
            )
        )
    return cases


def _context_lists(context: RetrievedContext) -> tuple[list[str], list[str]]:
    return (
        [hit["document"] for hit in context.design_doc_hits],
        [hit["document"] for hit in context.example_test_case_hits],
    )


def generate_test_cases_for_categories(
    condition_text: str,
    condition_id: str,
    context: RetrievedContext,
    categories: list[str],
    trace: str | None = None,
    module: str | None = None,
    provider: str | None = None,
    existing_ids: set[str] | None = None,
    id_prefix: str | None = None,
) -> list[TestCase]:
    design_doc_context, style_examples = _context_lists(context)
    prompt = build_targeted_generation_user_prompt(condition_text, design_doc_context, style_examples, categories)
    client = LLMClient(provider=provider)
    response = client.complete(prompt=prompt, system=GENERATION_SYSTEM_PROMPT, temperature=0.3)
    return parse_test_cases(response, condition_id, trace, module=module, existing_ids=existing_ids, id_prefix=id_prefix)


def generate_test_cases(
    condition_text: str,
    condition_id: str,
    context: RetrievedContext,
    trace: str | None = None,
    module: str | None = None,
    provider: str | None = None,
    existing_ids: set[str] | None = None,
    id_prefix: str | None = None,
) -> list[TestCase]:
    design_doc_context, style_examples = _context_lists(context)
    prompt = build_generation_user_prompt(condition_text, design_doc_context, style_examples)
    client = LLMClient(provider=provider)
    response = client.complete(prompt=prompt, system=GENERATION_SYSTEM_PROMPT, temperature=0.3)
    return parse_test_cases(response, condition_id, trace, module=module, existing_ids=existing_ids, id_prefix=id_prefix)
