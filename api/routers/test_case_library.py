"""POST /library/import (CSV/XLSX upload), GET /library (search/browse),
GET /library/sessions (grouping for the Uploaded/Generated accordions),
GET /library/{id} — Screen 5 (Test Case Library)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from src import config
from src.ingestion.csv_test_case_loader import load_test_cases
from src.vectorstore.test_cases_store import count, get_by_id, list_all, list_sessions, query_similar, upsert

router = APIRouter(prefix="/library", tags=["test_case_library"])

RAW_DIR = Path(config.PROJECT_ROOT) / "data" / "raw"


@router.post("/import")
async def import_library(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".csv", ".xlsx", ".xlsm"):
        raise HTTPException(400, "Only .csv and .xlsx files are supported")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = RAW_DIR / f"{uuid.uuid4()}{suffix}"
    with open(tmp_path, "wb") as f:
        f.write(await file.read())

    try:
        cases = load_test_cases(tmp_path)
    except Exception as e:
        raise HTTPException(400, f"Could not parse file: {e}")

    # One session per import request, so this upload shows up as its own group
    # in the Library screen's "Uploaded Test Cases" accordion.
    session_id = str(uuid.uuid4())
    session_created_at = datetime.now(timezone.utc).isoformat()
    cases = [
        tc.model_copy(update={"session_id": session_id, "session_label": file.filename, "session_created_at": session_created_at})
        for tc in cases
    ]

    upsert(cases)
    return {"imported": len(cases), "total_in_library": count()}


@router.get("/sessions")
async def browse_sessions():
    return list_sessions()


@router.get("")
async def browse_library(q: str | None = None, module: str | None = None, session_id: str | None = None, n: int = 20):
    if q:
        return query_similar(q, n_results=n, module=module, session_id=session_id)
    return list_all(module=module, session_id=session_id, limit=n)


@router.get("/{test_case_id}")
async def get_library_case(test_case_id: str):
    case = get_by_id(test_case_id)
    if not case:
        raise HTTPException(404, "Test case not found in library")
    return case
