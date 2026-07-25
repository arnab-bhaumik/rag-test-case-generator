"""Bulk-imports old test cases from a CSV/Excel file into the old_test_cases
Chroma collection (the RAG style/pattern library).

Usage: python -m scripts.bulk_import_old_test_cases <path> [--sheet NAME]
"""

import argparse

from src.ingestion.csv_test_case_loader import load_test_cases
from src.vectorstore.test_cases_store import count, upsert


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Path to a .csv or .xlsx file of old test cases")
    parser.add_argument("--sheet", default=None, help="Sheet name (Excel only; defaults to the active sheet)")
    args = parser.parse_args()

    cases = load_test_cases(args.path, sheet=args.sheet)
    upsert(cases)
    print(f"Imported {len(cases)} test cases. Collection now has {count()} total.")


if __name__ == "__main__":
    main()
