"""Manually check retriever.py's combined (design_docs + old_test_cases)
output for a single condition, as if it came out of decomposer.py.

Usage: python -m scripts.query_retriever "some testable condition" [--module Payments]
"""

import argparse

from src.retrieval.retriever import retrieve_context


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text", help="A testable condition, e.g. 'Refund is rejected for orders older than 30 days'")
    parser.add_argument("--module", default=None)
    args = parser.parse_args()

    ctx = retrieve_context(args.text, module=args.module)

    print(f"Condition: {ctx.condition_text}\n")
    print(f"-- Design doc context ({len(ctx.design_doc_hits)}) --")
    for hit in ctx.design_doc_hits:
        meta = hit["metadata"]
        print(f"  [{meta['source_type']}:{meta['source_id']}] {meta['section'] or '(no heading)'} (module={meta['module']}, distance={hit['distance']:.4f})")

    print(f"\n-- Style examples from old_test_cases ({len(ctx.example_test_case_hits)}) --")
    for hit in ctx.example_test_case_hits:
        meta = hit["metadata"]
        print(f"  [{hit['id']}] {meta['title']} (module={meta['module']}, distance={hit['distance']:.4f})")


if __name__ == "__main__":
    main()
