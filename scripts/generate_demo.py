"""Demonstrates the full Sprint 4 flow: generate categorized test cases for a
condition, audit grounding, detect category gaps, and regenerate just the
gaps.

If a Groq/Claude key is configured in .env, this calls the real LLM at every
step. If not, it falls back to canned responses so the deterministic halves
(parse_test_cases/parse_audit_results/find_gaps) are still exercised —
useful for verifying the pipeline without live API access.

Usage: python -m scripts.generate_demo
"""

from src import config
from src.generation.coverage_auditor import audit_grounding, find_gaps, parse_audit_results, regenerate_gaps
from src.generation.generator import generate_test_cases, parse_test_cases
from src.models.schemas import Category
from src.retrieval.retriever import retrieve_context

CONDITION_ID = "payments_refund_design_doc::C1"
CONDITION_TEXT = "Refund button is disabled with an explanation for orders older than 30 days."
CONDITION_TRACE = "payments_refund_design_doc, AC-1"
MODULE = "Payments"

REQUIREMENT_TEXT = """\
Refund Eligibility: An order is eligible for a refund if it was placed within the last 30 days
and has not already been refunded. Digital goods that have been downloaded are not eligible.
Acceptance Criteria:
- Orders older than 30 days show a disabled 'Request refund' button with an explanation.
"""

# Deliberately covers only 5 of the 7 categories, so find_gaps() has real
# gaps (Security, Integration) to detect and regenerate_gaps() to fill.
CANNED_GENERATION_RESPONSE = """```json
[
  {"title": "Refund button disabled for a 31-day-old order", "preconditions": "Order was placed 31 days ago.",
   "steps": ["Open the order detail page for a 31-day-old order.", "Locate the refund button."],
   "expected_result": "The 'Request refund' button is disabled and shows an explanation that the return window has passed.",
   "category": "Positive", "priority": "Medium"},
  {"title": "Refund button enabled for a 29-day-old order", "preconditions": "Order was placed 29 days ago.",
   "steps": ["Open the order detail page for a 29-day-old order."],
   "expected_result": "The 'Request refund' button is enabled.",
   "category": "Negative", "priority": "Medium"},
  {"title": "Refund button state exactly at the 30-day boundary", "preconditions": "Order was placed exactly 30 days ago.",
   "steps": ["Open the order detail page for an order placed exactly 30 days ago."],
   "expected_result": "The 'Request refund' button is enabled, since 30 days is still within the window.",
   "category": "Boundary", "priority": "High"},
  {"title": "Refund button state when order age crosses the boundary mid-session", "preconditions": "Order is 29 days 23 hours old.",
   "steps": ["Open the order detail page just before the 30-day mark.", "Wait for the window to elapse without refreshing."],
   "expected_result": "The button state reflects the age at next page load, not stale client-side state.",
   "category": "Edge", "priority": "Low"},
  {"title": "Disabled refund button shows a zip-code-style validation on the explanation text", "preconditions": "Order older than 30 days.",
   "steps": ["Open the order detail page.", "Inspect the explanation text."],
   "expected_result": "The explanation text is non-empty and human-readable.",
   "category": "Data Validation", "priority": "Low"}
]
```"""

# Marks one case ungrounded on purpose, to demonstrate the grounded/needs-verification split.
CANNED_AUDIT_RESPONSE = """```json
[
  {"grounded": true, "reason": "Directly matches AC-1."},
  {"grounded": true, "reason": "Reasonable negative counterpart to AC-1."},
  {"grounded": true, "reason": "30 days inclusive is a defensible boundary reading."},
  {"grounded": false, "reason": "Requirement doesn't mention client-side staleness — this is invented, not stated."},
  {"grounded": true, "reason": "Explanation text existing is implied by AC-1."}
]
```"""

CANNED_REGENERATION_RESPONSE = """```json
[
  {"title": "Refund button state is unaffected by user role", "preconditions": "Order older than 30 days.",
   "steps": ["Log in as a customer and open the order.", "Log in as a support agent and open the same order."],
   "expected_result": "Both roles see the refund button disabled with the same explanation — no role-based bypass.",
   "category": "Security", "priority": "Medium"}
]
```"""
# Integration deliberately omitted — the model judged it doesn't apply to this condition,
# which regenerate_gaps() must tolerate rather than treat as an error.


def main():
    ctx = retrieve_context(CONDITION_TEXT, module=MODULE)
    has_key = bool(config.GROQ_API_KEY or config.ANTHROPIC_API_KEY)

    print(f"Condition: {CONDITION_TEXT}\n")

    if has_key:
        print(f"--- Generating (live LLM, provider={config.LLM_PROVIDER}) ---")
        cases = generate_test_cases(CONDITION_TEXT, CONDITION_ID, ctx, trace=CONDITION_TRACE)
    else:
        print("--- No LLM key configured — parsing a canned generation response instead (dry run) ---")
        cases = parse_test_cases(CANNED_GENERATION_RESPONSE, CONDITION_ID, trace=CONDITION_TRACE)

    print(f"Generated {len(cases)} cases:")
    for c in cases:
        print(f"  [{c.id}] ({c.category.value}) {c.title}")

    if has_key:
        print("\n--- Auditing grounding (live LLM) ---")
        cases = audit_grounding(cases, REQUIREMENT_TEXT)
    else:
        print("\n--- No LLM key configured — parsing a canned audit response instead (dry run) ---")
        cases = parse_audit_results(CANNED_AUDIT_RESPONSE, cases)

    for c in cases:
        flag = "grounded" if c.grounded else "NEEDS VERIFICATION"
        print(f"  [{c.id}] {flag} — {c.title}")

    gaps = find_gaps(cases)
    print(f"\n--- Coverage gaps: {[g.value for g in gaps] or 'none'} ---")

    if gaps:
        if has_key:
            print(f"--- Regenerating gaps (live LLM) ---")
            fill = regenerate_gaps(CONDITION_TEXT, CONDITION_ID, ctx, gaps, trace=CONDITION_TRACE)
        else:
            print("--- No LLM key configured — parsing a canned regeneration response instead (dry run) ---")
            fill = parse_test_cases(CANNED_REGENERATION_RESPONSE, CONDITION_ID, trace=CONDITION_TRACE)

        for c in fill:
            print(f"  [{c.id}] ({c.category.value}) {c.title}  [unaudited]")
        cases = cases + fill

    still_missing = find_gaps(cases)
    print(f"\nFinal set: {len(cases)} test cases across {len({c.category for c in cases})} categories.")
    print(f"Still-missing categories (may be genuinely not applicable): {[g.value for g in still_missing] or 'none'}")


if __name__ == "__main__":
    main()
