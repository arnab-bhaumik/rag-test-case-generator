"""Demonstrates decomposer.py end to end.

If a Groq/Claude key is configured in .env, this calls the real LLM. If not,
it falls back to a canned response so build_user_prompt()/parse_conditions()
(the deterministic half of decomposer.py) are still exercised — useful for
verifying the parsing logic without live API access.

Usage: python -m scripts.decompose_demo
"""

from src import config
from src.generation.decomposer import build_user_prompt, decompose, parse_conditions
from src.retrieval.retriever import retrieve_context

REQUIREMENT_ID = "payments_refund_design_doc"
REQUIREMENT_MODULE = "Payments"
REQUIREMENT_TEXT = """\
Refund Eligibility: An order is eligible for a refund if it was placed within the last 30 days
and has not already been refunded. Digital goods that have been downloaded are not eligible.
Acceptance Criteria:
- Orders older than 30 days show a disabled 'Request refund' button with an explanation.
- Downloaded digital goods are excluded from refund eligibility.
- Only one refund can be issued per order.

Refund Processing: Once a refund is approved, the amount is credited back to the original
payment method within 5-7 business days. The order status changes to 'Refunded' and the
customer receives a confirmation email.
Acceptance Criteria:
- Refund amount always matches the original charge amount exactly.
- The order status updates to 'Refunded' immediately after approval.
- A confirmation email is sent within 1 minute of refund approval.
"""

# Stands in for a real LLM response when no key is configured — same shape
# decomposer.parse_conditions() expects, so the parsing path is still verified.
CANNED_RESPONSE = """```json
[
  {"text": "Refund button is disabled with an explanation for orders older than 30 days.", "ac_ref": "AC-1"},
  {"text": "Downloaded digital goods cannot be refunded.", "ac_ref": "AC-2"},
  {"text": "An order cannot be refunded more than once.", "ac_ref": "AC-3"},
  {"text": "Refunded amount exactly matches the original charge amount.", "ac_ref": "AC-4"},
  {"text": "Order status updates to 'Refunded' immediately after refund approval.", "ac_ref": "AC-5"},
  {"text": "A confirmation email is sent within 1 minute of refund approval.", "ac_ref": "AC-6"}
]
```"""


def main():
    print("--- Prompt that would be sent ---")
    print(build_user_prompt(REQUIREMENT_TEXT))
    print()

    has_key = bool(config.GROQ_API_KEY or config.ANTHROPIC_API_KEY)
    if has_key:
        print(f"--- Calling live LLM (provider={config.LLM_PROVIDER}) ---")
        conditions = decompose(REQUIREMENT_TEXT, REQUIREMENT_ID)
    else:
        print("--- No LLM key configured — parsing a canned response instead (dry run) ---")
        conditions = parse_conditions(CANNED_RESPONSE, REQUIREMENT_ID)

    print()
    print("--- Conditions with retrieved context (retriever.py) ---")
    for c in conditions:
        print(f"\n[{c.id}] ({c.ac_ref or 'no AC ref'}) {c.text}")
        ctx = retrieve_context(c.text, module=REQUIREMENT_MODULE, n_design_docs=2, n_examples=2)
        for hit in ctx.design_doc_hits:
            meta = hit["metadata"]
            print(f"    doc context: [{meta['source_id']}] {meta['section'] or '(no heading)'} (distance={hit['distance']:.3f})")
        for hit in ctx.example_test_case_hits:
            meta = hit["metadata"]
            print(f"    style example: [{hit['id']}] {meta['title']} (distance={hit['distance']:.3f})")


if __name__ == "__main__":
    main()
