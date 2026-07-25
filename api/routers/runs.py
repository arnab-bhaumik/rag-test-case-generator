"""POST /runs, GET /runs, GET /runs/{id}, GET /runs/{id}/status."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from src import config
from src.models.schemas import Run
from src.pipeline import RUNS, execute_run, new_run

router = APIRouter(prefix="/runs", tags=["runs"])

RAW_DIR = Path(config.PROJECT_ROOT) / "data" / "raw"


@router.post("", status_code=201, response_model=Run)
async def create_run(
    background_tasks: BackgroundTasks,
    source_type: str = Form(...),
    ticket_key: str | None = Form(None),
    module: str | None = Form(None),
    scope: str | None = Form(None),
    id_prefix: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    if source_type not in ("jira", "doc"):
        raise HTTPException(400, "source_type must be 'jira' or 'doc'")

    doc_path: str | None = None
    if source_type == "jira":
        if not ticket_key:
            raise HTTPException(400, "ticket_key is required for source_type=jira")
        source_id = ticket_key
    else:
        if not file:
            raise HTTPException(400, "file is required for source_type=doc")
        if Path(file.filename).suffix.lower() not in (".pdf", ".docx"):
            raise HTTPException(400, "Only .pdf and .docx are supported")
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        doc_path = str(RAW_DIR / f"{uuid.uuid4()}_{file.filename}")
        with open(doc_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        source_id = Path(file.filename).stem

    run = new_run(source_type, source_id, module, scope=scope, id_prefix=id_prefix)
    background_tasks.add_task(execute_run, run.id, doc_path)
    return run


@router.get("", response_model=list[Run])
async def list_runs():
    return sorted(RUNS.values(), key=lambda r: r.created_at, reverse=True)


@router.get("/{run_id}", response_model=Run)
async def get_run(run_id: str):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/{run_id}/status")
async def get_run_status(run_id: str):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return {"id": run.id, "status": run.status, "steps": run.steps, "error": run.error}
