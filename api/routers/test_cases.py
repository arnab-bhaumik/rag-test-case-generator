"""PATCH /test-cases/{id}, bulk approve/reject, single-case regenerate."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.generation.coverage_auditor import audit_grounding
from src.generation.generator import generate_test_cases
from src.models.schemas import Priority, ReviewStatus, Run, TestCase
from src.pipeline import RUNS
from src.retrieval.retriever import retrieve_context
from src.vectorstore.test_cases_store import get_by_id as get_library_case
from src.vectorstore.test_cases_store import upsert as upsert_library

router = APIRouter(prefix="/test-cases", tags=["test_cases"])


def _find_case(test_case_id: str) -> tuple[TestCase, Run, int]:
    for run in RUNS.values():
        for i, tc in enumerate(run.test_cases):
            if tc.id == test_case_id:
                return tc, run, i
    raise HTTPException(404, "Test case not found")


class TestCaseUpdate(BaseModel):
    id: str | None = None
    title: str | None = None
    description: str | None = None
    preconditions: str | None = None
    steps: list[str] | None = None
    expected_result: str | None = None
    priority: Priority | None = None
    manually_verified: bool | None = None
    # Only "unreviewed" is allowed here (the "Undo reject" action) — setting
    # "approved" must go through bulk_approve below so the grounding gate has
    # exactly one enforcement point, not one per call site.
    status: Literal["unreviewed"] | None = None


def validate_id_change(new_id: str, current_id: str, other_ids_in_run: list[str], library_hit: dict | None) -> str | None:
    """Pure validation, extracted for direct unit testing (no Run/Chroma
    needed) — mirrors this file's other pure-logic-extraction pattern (see
    export.py's _export_status). Returns an error message, or None if the
    change is allowed. A collision with the library is only a real conflict
    if that library entry belongs to a *different* case — re-approving the
    same case after an edit naturally finds itself there."""
    new_id = new_id.strip()
    if not new_id:
        return "Test Case ID cannot be empty"
    if new_id == current_id:
        return None
    if new_id in other_ids_in_run:
        return f'"{new_id}" is already used by another test case in this run.'
    if library_hit is not None and library_hit.get("id") != current_id:
        return f'"{new_id}" is already used by a different test case in the library.'
    return None


@router.patch("/{test_case_id}", response_model=TestCase)
async def update_test_case(test_case_id: str, update: TestCaseUpdate):
    tc, run, i = _find_case(test_case_id)
    patch = update.model_dump(exclude_unset=True)
    if not patch:
        return tc

    if "id" in patch:
        new_id = (patch["id"] or "").strip()
        other_ids = [c.id for c in run.test_cases if c.id != tc.id]
        library_hit = get_library_case(new_id) if new_id and new_id != tc.id else None
        error = validate_id_change(new_id, tc.id, other_ids, library_hit)
        if error:
            status_code = 400 if "cannot be empty" in error else 409
            raise HTTPException(status_code, error)
        patch["id"] = new_id

    if patch.keys() - {"manually_verified", "status"}:
        patch["edited"] = True
    tc = tc.model_copy(update=patch)
    run.test_cases[i] = tc
    return tc


class BulkIds(BaseModel):
    ids: list[str]


@router.post("/bulk-approve")
async def bulk_approve(body: BulkIds):
    approved: list[TestCase] = []
    blocked: list[str] = []
    for test_case_id in body.ids:
        tc, run, i = _find_case(test_case_id)
        if not tc.grounded and not tc.manually_verified:
            blocked.append(tc.id)  # same gate Screen 2 enforces client-side
            continue
        tc = tc.model_copy(
            update={
                "status": ReviewStatus.approved,
                # One session per run, so every case approved out of the same run
                # groups together in the Library screen's "Generated" accordion.
                "session_id": run.id,
                "session_label": run.source_id,
                "session_created_at": run.created_at,
            }
        )
        run.test_cases[i] = tc
        approved.append(tc)
    if approved:
        upsert_library(approved)  # write-back into the old_test_cases pattern library
    return {"approved": approved, "blocked": blocked}


@router.post("/bulk-reject")
async def bulk_reject(body: BulkIds):
    rejected: list[TestCase] = []
    for test_case_id in body.ids:
        tc, run, i = _find_case(test_case_id)
        tc = tc.model_copy(update={"status": ReviewStatus.rejected})
        run.test_cases[i] = tc
        rejected.append(tc)
    return {"rejected": rejected}


@router.post("/{test_case_id}/regenerate", response_model=list[TestCase])
async def regenerate_test_case(test_case_id: str):
    tc, run, i = _find_case(test_case_id)
    condition = next((c for c in run.conditions if c.id == tc.condition_id), None)
    if not condition:
        raise HTTPException(400, "Cannot regenerate: source condition not found for this run")

    ctx = retrieve_context(condition.text, module=run.module)
    existing_ids = {c.id for r in RUNS.values() for c in r.test_cases if c.id != test_case_id}
    try:
        new_cases = generate_test_cases(
            condition.text, condition.id, ctx, trace=tc.trace, module=run.module, existing_ids=existing_ids, id_prefix=run.id_prefix
        )
        new_cases = audit_grounding(new_cases, run.requirement_text)
    except Exception as e:
        # The original case is untouched at this point (run.test_cases isn't
        # mutated until after this succeeds) — surface a clear error instead
        # of an opaque 500 so the user knows to retry rather than assume the
        # case is now broken.
        raise HTTPException(502, f"Regeneration failed: {e}")

    run.test_cases = [c for c in run.test_cases if c.id != test_case_id] + new_cases
    return new_cases
