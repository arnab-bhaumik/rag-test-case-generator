"""Ingests the Sprint 2 sample design docs (DOCX + PDF) and a synthetic Jira
ticket into the design_docs collection.

No live Jira credentials are configured yet (see plan.md §2), so the ticket
is a hardcoded Atlassian Document Format (ADF) payload standing in for a real
`get_issue_content()` call — it exercises the same adf_to_text() parsing path.

Usage: python -m scripts.ingest_sample_docs
"""

from pathlib import Path

from src.ingestion.chunker import chunk_sections, chunk_text
from src.ingestion.doc_parser import parse_document
from src.ingestion.jira_client import adf_to_text, extract_acceptance_criteria
from src.vectorstore.design_docs_store import count, upsert

SAMPLE_DOCS = [
    ("data/sample/payments_refund_design_doc.docx", "Payments"),
    ("data/sample/search_filtering_design_doc.pdf", "Search"),
]

SYNTHETIC_TICKET_KEY = "DEMO-101"
SYNTHETIC_TICKET_MODULE = "Auth"
SYNTHETIC_ADF_DESCRIPTION = {
    "type": "doc",
    "content": [
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "Users should be able to reset a forgotten password via an emailed link.",
                }
            ],
        },
        {"type": "heading", "content": [{"type": "text", "text": "Acceptance Criteria"}]},
        {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Reset link expires after 30 minutes."}],
                        }
                    ],
                },
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Reset link can only be used once."}],
                        }
                    ],
                },
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "After reset, all other active sessions are logged out.",
                                }
                            ],
                        }
                    ],
                },
            ],
        },
    ],
}


def ingest_docs():
    for path, module in SAMPLE_DOCS:
        sections = parse_document(path)
        chunks = chunk_sections(sections, source_type="doc", source_id=Path(path).stem, module=module)
        upsert(chunks)
        print(f"{path}: {len(sections)} sections -> {len(chunks)} chunks (module={module})")


def ingest_synthetic_ticket():
    description = adf_to_text(SYNTHETIC_ADF_DESCRIPTION).strip()
    ac = extract_acceptance_criteria(description)
    chunks = chunk_text(
        description,
        source_type="jira",
        source_id=SYNTHETIC_TICKET_KEY,
        section="Description",
        module=SYNTHETIC_TICKET_MODULE,
    )
    upsert(chunks)
    print(f"{SYNTHETIC_TICKET_KEY}: {len(chunks)} chunks (acceptance criteria detected: {bool(ac)})")


if __name__ == "__main__":
    ingest_docs()
    ingest_synthetic_ticket()
    print(f"design_docs collection now has {count()} total chunks")
