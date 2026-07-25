"""GET /runs/{id}/coverage, POST /runs/{id}/gaps/{category}/acknowledge,
POST /runs/{id}/gaps/{category}/generate."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.models.schemas import Category, Run, TestCase
from src.pipeline import RUNS, fill_gap_category
from src.traceability.rtm_builder import build_rtm

router = APIRouter(prefix="/runs", tags=["coverage"])


def _get_run(run_id: str) -> Run:
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/{run_id}/coverage")
async def get_coverage(run_id: str):
    run = _get_run(run_id)
    return {"rtm": build_rtm(run.conditions, run.test_cases), "gaps": run.gaps}


@router.post("/{run_id}/gaps/{category}/acknowledge")
async def acknowledge_gap(run_id: str, category: Category):
    run = _get_run(run_id)
    for gap in run.gaps:
        if gap.category == category:
            gap.acknowledged = True
            return gap
    raise HTTPException(404, "No such gap on this run")


@router.post("/{run_id}/gaps/{category}/generate", response_model=list[TestCase])
async def generate_gap(run_id: str, category: Category):
    run = _get_run(run_id)
    new_cases = fill_gap_category(run, category)
    if not new_cases:
        raise HTTPException(422, "No cases could be generated — this category may genuinely not apply here")
    return new_cases
