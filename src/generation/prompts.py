"""System prompts for generation and coverage audit. The 7-category taxonomy
here must stay in sync with models.schemas.Category and
UX Screen/Screen2-ReviewQueue.dc.html's CATEGORY_ORDER."""

from __future__ import annotations

from src.models.schemas import Category

ALL_CATEGORIES = [c.value for c in Category]

GENERATION_SYSTEM_PROMPT = f"""You are a senior QA engineer writing test cases for a single atomic testable \
condition extracted from a software requirement.

Write test cases across as many of these categories as genuinely apply to this condition — do not force a \
category that doesn't make sense here, but do not skip one that clearly does:
{", ".join(ALL_CATEGORIES)}

Style: match the tone, granularity, and step format of the "style examples" you're given — those are real \
test cases this team has written before.

Each test case object must have these exact keys:
- title (string) — a short test scenario name, e.g. "Login fails with expired password"
- description (string) — one sentence stating the test objective: what this case verifies and why it matters
- preconditions (string)
- steps (array of imperative action strings)
- expected_result (string)
- category (one of the categories listed above, exactly)
- priority ("High", "Medium", or "Low")

Return ONLY a valid JSON array of test case objects. No prose, no markdown code fences."""

AUDIT_SYSTEM_PROMPT = """You are auditing a batch of generated test cases against the original requirement \
text they claim to test. For EACH test case, decide if it is "grounded" — its steps and expected result are \
a reasonable, defensible interpretation of the requirement text, not invented or contradicted by it.

Return ONLY a valid JSON array, one object per input test case IN THE SAME ORDER, with keys:
"grounded" (boolean) and "reason" (a short string explaining the verdict)."""


def build_generation_user_prompt(
    condition_text: str, design_doc_context: list[str], style_examples: list[str]
) -> str:
    context_block = "\n\n".join(design_doc_context) or "(no additional design doc context retrieved)"
    examples_block = "\n\n".join(style_examples) or "(no style examples retrieved)"
    return f"""Condition to test:
{condition_text}

Relevant design doc context:
{context_block}

Style examples from this team's existing test cases:
{examples_block}

Write test cases for this condition as a JSON array."""


def build_targeted_generation_user_prompt(
    condition_text: str,
    design_doc_context: list[str],
    style_examples: list[str],
    categories: list[str],
) -> str:
    context_block = "\n\n".join(design_doc_context) or "(no additional design doc context retrieved)"
    examples_block = "\n\n".join(style_examples) or "(no style examples retrieved)"
    categories_block = ", ".join(categories)
    return f"""Condition to test:
{condition_text}

Relevant design doc context:
{context_block}

Style examples from this team's existing test cases:
{examples_block}

Write test cases ONLY for these categories: {categories_block}
If a category genuinely does not apply to this condition, return an empty array for it rather than forcing \
an irrelevant case — an empty result for a category is a valid, honest answer.

Return as a JSON array."""


def build_audit_user_prompt(requirement_text: str, test_case_summaries: list[str]) -> str:
    cases_block = "\n".join(f"{i + 1}. {summary}" for i, summary in enumerate(test_case_summaries))
    return f"""Requirement text:
{requirement_text}

Test cases to audit:
{cases_block}

Audit each test case as a JSON array."""
