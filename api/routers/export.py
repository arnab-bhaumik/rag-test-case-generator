"""GET /export/{run_id}/status, POST /export/excel, POST /export/jira.

Gating: blocks only when there are 0 approved cases — nothing to export.
Pending verification and unacknowledged gaps elsewhere in the run are
surfaced as a non-blocking `note`, not a hard block. The original design
(mockup text: "Export is disabled: 0 approved, 1 needs verification, 2 gaps
unacknowledged") blocked on all three; that made large runs (hundreds of
cases) impossible to partially ship — you couldn't export the handful
already approved until the entire backlog was triaged. Changed after this
surfaced in real usage."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from src.export.excel_exporter import export_to_bytes
from src.export.jira_uploader import upload_test_cases
from src.models.schemas import ReviewStatus, Run
from src.pipeline import RUNS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


def _get_run(run_id: str) -> Run:
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


def _export_status(run: Run) -> dict:
    approved = [tc for tc in run.test_cases if tc.status == ReviewStatus.approved]
    needs_verification = [tc for tc in run.test_cases if tc.status == ReviewStatus.unreviewed and not tc.grounded and not tc.manually_verified]
    unacknowledged_gaps = [g for g in run.gaps if not g.acknowledged]

    blocked = not approved
    reason = "Export is disabled: 0 approved test cases." if blocked else None

    notes = []
    if needs_verification:
        notes.append(f"{len(needs_verification)} case{'s' if len(needs_verification) != 1 else ''} still need{'s' if len(needs_verification) == 1 else ''} manual verification")
    if unacknowledged_gaps:
        notes.append(f"{len(unacknowledged_gaps)} coverage gap{'s' if len(unacknowledged_gaps) != 1 else ''} unacknowledged")
    note = f"{', '.join(notes)}. Only the {len(approved)} approved case{'s' if len(approved) != 1 else ''} will be exported." if notes and not blocked else None

    return {
        "approved_count": len(approved),
        "blocked": blocked,
        "reason": reason,
        "note": note,
    }


@router.get("/{run_id}/status")
async def export_status(run_id: str):
    return _export_status(_get_run(run_id))


class ExcelExportRequest(BaseModel):
    run_id: str


@router.post("/excel")
async def export_excel(body: ExcelExportRequest):
    run = _get_run(body.run_id)
    status = _export_status(run)
    if status["blocked"]:
        raise HTTPException(422, status["reason"])

    data = export_to_bytes(run)
    filename = f"{run.source_id}_test_cases.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class JiraExportRequest(BaseModel):
    run_id: str
    test_case_ids: list[str] | None = None  # None = every approved case not already uploaded


@router.post("/jira")
async def export_jira(body: JiraExportRequest):
    run = _get_run(body.run_id)
    status = _export_status(run)
    if status["blocked"]:
        raise HTTPException(422, status["reason"])

    if body.test_case_ids is not None:
        targets = [tc for tc in run.test_cases if tc.id in body.test_case_ids]
    else:
        targets = [tc for tc in run.test_cases if tc.status == ReviewStatus.approved and not tc.jira_key]

    source_ticket_key = run.source_id if run.source_type == "jira" else None
    logger.info("Run %s: uploading %d test cases to Jira", body.run_id, len(targets))
    results = upload_test_cases(targets, source_ticket_key)

    by_id = {r["test_case_id"]: r for r in results if r["success"]}
    run.test_cases = [tc.model_copy(update={"jira_key": by_id[tc.id]["jira_key"]}) if tc.id in by_id else tc for tc in run.test_cases]

    fail_count = len(results) - len(by_id)
    logger.info("Run %s: Jira upload finished — %d succeeded, %d failed", body.run_id, len(by_id), fail_count)
    return results
