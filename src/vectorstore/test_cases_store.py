"""CRUD for the old_test_cases Chroma collection — the RAG style/pattern
library that retrieval draws on for both similar-case examples and module
coverage history."""

from __future__ import annotations

import re

from src.embeddings.embedder import get_embedding_function
from src.models.schemas import TestCase
from src.vectorstore.chroma_client import get_client

COLLECTION_NAME = "old_test_cases"

UNSORTED_SESSION_ID = "__unsorted__"


def _collection():
    return get_client().get_or_create_collection(COLLECTION_NAME, embedding_function=get_embedding_function())


def _document(tc: TestCase) -> str:
    steps = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(tc.steps))
    return (
        f"Title: {tc.title}\n"
        f"Description: {tc.description}\n"
        f"Preconditions: {tc.preconditions}\n"
        f"Steps:\n{steps}\n"
        f"Expected Result: {tc.expected_result}"
    )


_DOCUMENT_RE = re.compile(
    r"Title: .*?\n"
    r"(?:Description: (?P<description>.*?)\n)?"
    r"Preconditions: (?P<preconditions>.*?)\n"
    r"Steps:\n(?P<steps>.*?)\n"
    r"Expected Result: (?P<expected_result>.*)",
    re.DOTALL,
)
_STEP_LINE_RE = re.compile(r"^\d+\. ", re.MULTILINE)


def _parse_document(document: str) -> dict:
    """Reverses _document() so description/preconditions/steps/expected_result can
    be shown in full in the UI without duplicating them into metadata. The
    Description line is optional in the pattern — entries written before that
    field existed have no such line, and still parse correctly (as description="")."""
    match = _DOCUMENT_RE.match(document)
    if not match:
        return {"description": "", "preconditions": "", "steps": [], "expected_result": ""}
    steps_block = match.group("steps")
    steps = [_STEP_LINE_RE.sub("", line, count=1) for line in steps_block.splitlines() if line.strip()]
    return {
        "description": match.group("description") or "",
        "preconditions": match.group("preconditions"),
        "steps": steps,
        "expected_result": match.group("expected_result"),
    }


def _with_document_fields(entry: dict) -> dict:
    entry.update(_parse_document(entry["document"]))
    return entry


def upsert(cases: list[TestCase]) -> None:
    if not cases:
        return
    _collection().upsert(
        ids=[tc.id for tc in cases],
        documents=[_document(tc) for tc in cases],
        metadatas=[
            {
                "title": tc.title,
                "module": tc.module or "",
                "priority": tc.priority.value,
                "source": tc.source,
                "session_id": tc.session_id or "",
                "session_label": tc.session_label or "",
                "session_created_at": tc.session_created_at or "",
            }
            for tc in cases
        ],
    )


def _where(module: str | None, session_id: str | None) -> dict | None:
    clauses = []
    if module:
        clauses.append({"module": module})
    if session_id:
        if session_id.startswith(f"{UNSORTED_SESSION_ID}:"):
            # Pseudo id minted by list_sessions() for legacy entries with no real
            # session_id — split back into "no session_id" + "matches this source".
            clauses.append({"session_id": ""})
            clauses.append({"source": session_id.removeprefix(f"{UNSORTED_SESSION_ID}:")})
        else:
            clauses.append({"session_id": session_id})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def query_similar(text: str, n_results: int = 5, module: str | None = None, session_id: str | None = None) -> list[dict]:
    result = _collection().query(
        query_texts=[text],
        n_results=n_results,
        where=_where(module, session_id),
    )
    return [
        _with_document_fields(
            {
                "id": result["ids"][0][i],
                "document": result["documents"][0][i],
                "metadata": result["metadatas"][0][i],
                "distance": result["distances"][0][i],
            }
        )
        for i in range(len(result["ids"][0]))
    ]


def list_all(module: str | None = None, session_id: str | None = None, limit: int = 100) -> list[dict]:
    """Plain listing (no similarity query) for browsing — Screen 5's default view."""
    result = _collection().get(where=_where(module, session_id), limit=limit)
    return [
        _with_document_fields({"id": result["ids"][i], "document": result["documents"][i], "metadata": result["metadatas"][i]})
        for i in range(len(result["ids"]))
    ]


def get_by_id(test_case_id: str) -> dict | None:
    result = _collection().get(ids=[test_case_id])
    if not result["ids"]:
        return None
    return _with_document_fields({"id": result["ids"][0], "document": result["documents"][0], "metadata": result["metadatas"][0]})


def count() -> int:
    return _collection().count()


_ID_SUFFIX_RE = re.compile(r"_(\d+)$")


def normalize_module_for_id(module: str | None) -> str:
    """"Payments" -> "PAYMENTS", "Payment Gateway" -> "PAYMENT_GATEWAY", blank/None -> "NOT_DEFINED"."""
    module = (module or "").strip()
    if not module:
        return "NOT_DEFINED"
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", module).strip("_").upper()
    return normalized or "NOT_DEFINED"


def build_id_prefix(module: str | None) -> str:
    return f"TC_{normalize_module_for_id(module)}_"


def _max_sequence_number(prefix: str, ids) -> int:
    best = 0
    for id_ in ids:
        if id_.startswith(prefix):
            m = _ID_SUFFIX_RE.search(id_)
            if m:
                best = max(best, int(m.group(1)))
    return best


def next_sequence_ids(
    module: str | None, count: int, extra_existing_ids: set[str] | None = None, custom_prefix: str | None = None
) -> list[str]:
    """Mints `count` new ids, continuing from the highest number already used
    with this exact prefix. Checks both the persisted library and
    `extra_existing_ids` — the latter covers cases already minted earlier in
    the same run that haven't been approved into the library yet, so a run
    never collides with its own not-yet-approved siblings.

    Prefix is `custom_prefix` verbatim if the user supplied one on the
    Generate screen (e.g. "DEMND002_Reg_TC_" — used exactly as typed, no
    separator inserted), else the module-derived TC_{MODULE}_ default
    ("NOT_DEFINED" if no module either)."""
    if count <= 0:
        return []
    prefix = custom_prefix if custom_prefix else build_id_prefix(module)
    library_ids = (row["id"] for row in list_all(limit=10_000))
    start = max(_max_sequence_number(prefix, library_ids), _max_sequence_number(prefix, extra_existing_ids or set()))
    return [f"{prefix}{start + i + 1:03d}" for i in range(count)]


def list_sessions(limit: int = 10_000) -> list[dict]:
    """Groups every library entry by its session_id for the Test Case Library
    screen's Uploaded/Generated accordions. Entries with no session_id (written
    before this field existed) are bucketed under UNSORTED_SESSION_ID. Chroma has
    no native GROUP BY, so this fetches everything and aggregates in Python —
    fine at library scale (mirrors modules.py's _derived_modules() pattern)."""
    result = _collection().get(limit=limit)
    sessions: dict[str, dict] = {}
    backfill_ids: list[str] = []
    backfill_metas: list[dict] = []
    for i in range(len(result["ids"])):
        meta = result["metadatas"][i]
        if "session_id" not in meta:
            # Chroma's equality filter only matches documents where the key is
            # present — a doc predating this field has no key at all, not an
            # empty one, so _where()'s {"session_id": ""} filter would silently
            # skip it forever. Stamp the key in so it's actually filterable.
            meta = {**meta, "session_id": "", "session_label": "", "session_created_at": ""}
            backfill_ids.append(result["ids"][i])
            backfill_metas.append(meta)
        source = meta.get("source", "")
        real_session_id = meta.get("session_id")
        # Legacy entries share no real session_id — bucket per source so an unsorted
        # upload doesn't get lumped in with unsorted generated cases under one type.
        session_id = real_session_id or f"{UNSORTED_SESSION_ID}:{source}"
        if session_id not in sessions:
            sessions[session_id] = {
                "session_id": session_id,
                "session_label": meta.get("session_label") or "Unsorted (before session tracking)",
                "session_created_at": meta.get("session_created_at") or "",
                "source": source,
                "count": 0,
            }
        sessions[session_id]["count"] += 1
    if backfill_ids:
        _collection().update(ids=backfill_ids, metadatas=backfill_metas)
    return sorted(sessions.values(), key=lambda s: s["session_created_at"], reverse=True)


def rename_module(old: str, new: str) -> int:
    """Bulk-updates every stored test case tagged `old` to `new` — metadata
    only, via Chroma's update() rather than upsert(), so it doesn't need to
    recompute embeddings for documents whose text isn't changing. Returns
    how many were updated."""
    matches = _collection().get(where={"module": old})
    ids = matches["ids"]
    if not ids:
        return 0
    metadatas = matches["metadatas"]
    for m in metadatas:
        m["module"] = new
    _collection().update(ids=ids, metadatas=metadatas)
    return len(ids)
