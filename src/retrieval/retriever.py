"""For a single testable condition, retrieves both halves plan.md §5 step 4
calls for: design_docs (requirement context) and old_test_cases (style
examples + module history) — module-scoped payload filtering plus a
lightweight lexical rerank on top of vector similarity.

External rerank APIs (Cohere/Voyage) are optional and not required to start
(plan.md §2) — this rerank is a cheap keyword-overlap nudge, not a
cross-encoder.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.vectorstore.design_docs_store import query_similar as query_design_docs
from src.vectorstore.test_cases_store import query_similar as query_old_test_cases

RERANK_WEIGHT = 0.15
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class RetrievedContext:
    condition_text: str
    design_doc_hits: list[dict] = field(default_factory=list)
    example_test_case_hits: list[dict] = field(default_factory=list)


def _keyword_overlap(query: str, document: str) -> float:
    q_tokens = set(_TOKEN_RE.findall(query.lower()))
    if not q_tokens:
        return 0.0
    d_tokens = set(_TOKEN_RE.findall(document.lower()))
    return len(q_tokens & d_tokens) / len(q_tokens)


def _rerank(hits: list[dict], query: str) -> list[dict]:
    """Nudges vector-similarity order using lexical overlap with the query —
    lower distance is better, so overlap subtracts from it."""
    return sorted(hits, key=lambda hit: hit["distance"] - RERANK_WEIGHT * _keyword_overlap(query, hit["document"]))


def retrieve_context(
    condition_text: str,
    module: str | None = None,
    n_design_docs: int = 5,
    n_examples: int = 5,
) -> RetrievedContext:
    design_hits = query_design_docs(condition_text, n_results=n_design_docs, module=module)
    example_hits = query_old_test_cases(condition_text, n_results=n_examples, module=module)

    return RetrievedContext(
        condition_text=condition_text,
        design_doc_hits=_rerank(design_hits, condition_text),
        example_test_case_hits=_rerank(example_hits, condition_text),
    )
