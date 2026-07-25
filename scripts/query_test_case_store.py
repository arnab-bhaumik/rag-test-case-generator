"""Manually query the old_test_cases store to sanity-check retrieval quality.

Usage: python -m scripts.query_test_case_store "some search text" [--module Auth] [-n 5]
"""

import argparse

from src.vectorstore.test_cases_store import query_similar


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text", help="Free-text query")
    parser.add_argument("--module", default=None)
    parser.add_argument("-n", type=int, default=5)
    args = parser.parse_args()

    hits = query_similar(args.text, n_results=args.n, module=args.module)
    for i, hit in enumerate(hits, 1):
        print(f"{i}. [{hit['id']}] {hit['metadata']['title']} (module={hit['metadata']['module']}, distance={hit['distance']:.4f})")


if __name__ == "__main__":
    main()
