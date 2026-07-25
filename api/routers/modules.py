"""GET /modules — union of the manually-maintained list (src/modules_store.py)
and the modules already stored on old_test_cases (the derived list plan.md §7
originally settled on). POST/PATCH/DELETE for full CRUD on the manual list."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src import modules_store
from src.vectorstore.test_cases_store import list_all, rename_module

router = APIRouter(prefix="/modules", tags=["modules"])


def _derived_modules() -> set[str]:
    cases = list_all(limit=10_000)
    return {c["metadata"]["module"] for c in cases if c["metadata"].get("module")}


def _all_modules() -> list[str]:
    return sorted(_derived_modules() | set(modules_store.list_manual()))


@router.get("")
async def list_modules() -> list[str]:
    return _all_modules()


class ModuleCreate(BaseModel):
    name: str


@router.post("")
async def create_module(body: ModuleCreate) -> list[str]:
    try:
        modules_store.add(body.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _all_modules()


@router.delete("/{name}")
async def delete_module(name: str) -> list[str]:
    if name in _derived_modules():
        raise HTTPException(
            409,
            f'"{name}" is still used by existing test cases, so it can\'t be deleted — rename it instead if you want to consolidate.',
        )
    modules_store.remove(name)
    return _all_modules()


class ModuleRename(BaseModel):
    new_name: str


@router.patch("/{name}")
async def rename_module_route(name: str, body: ModuleRename):
    try:
        modules_store.rename(name, body.new_name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # Cascades into the library's persisted data; in-progress runs already
    # in memory keep whatever module tag they were generated with — a rename
    # only affects the library going forward, not live runs.
    renamed_count = rename_module(name, body.new_name.strip())
    return {"renamed_test_cases": renamed_count, "modules": _all_modules()}
