"""Manually query the design_docs store to sanity-check retrieval quality.

Usage: python -m scripts.query_design_docs "some search text" [--source-id NAME] [-n 5]
"""

import argparse

from src.vectorstore.design_docs_store import query_similar


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text", help="Free-text query")
    parser.add_argument("--source-id", default=None)
    parser.add_argument("--source-type", default=None, choices=["doc", "jira"])
    parser.add_argument("-n", type=int, default=5)
    args = parser.parse_args()

    hits = query_similar(args.text, n_results=args.n, source_id=args.source_id, source_type=args.source_type)
    for i, hit in enumerate(hits, 1):
        meta = hit["metadata"]
        section = meta["section"] or "(no heading)"
        print(f"{i}. [{meta['source_type']}:{meta['source_id']}] {section} (distance={hit['distance']:.4f})")
        print(f"   {hit['document'][:140].replace(chr(10), ' ')}...")


if __name__ == "__main__":
    main()
