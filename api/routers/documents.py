"""POST /documents/detect-changes — pre-generation helper for the Generate
screen's Scope box: scans an uploaded DOCX for red-marked text (a common
convention when a design doc is reused across releases) and returns it so
the frontend can pre-fill Scope, not silently filter on it."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from src import config
from src.ingestion.doc_parser import detect_red_text

router = APIRouter(prefix="/documents", tags=["documents"])

RAW_DIR = Path(config.PROJECT_ROOT) / "data" / "raw"


@router.post("/detect-changes")
async def detect_changes(file: UploadFile = File(...)):
    if Path(file.filename).suffix.lower() != ".docx":
        return {"detected_text": ""}  # PDFs/other types: no detection support yet, not an error

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = RAW_DIR / f"{uuid.uuid4()}_{file.filename}"
    try:
        with open(tmp_path, "wb") as f:
            f.write(await file.read())
        detected = detect_red_text(tmp_path)
    except Exception as e:
        raise HTTPException(400, f"Could not scan file: {e}")
    finally:
        # Purely a scan, not part of a run — this file has no further use,
        # unlike runs.py's doc_path which the background task still needs.
        tmp_path.unlink(missing_ok=True)

    return {"detected_text": detected}
