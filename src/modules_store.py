"""Manually-maintained module list, merged (by api/routers/modules.py) with
the modules already present on old_test_cases — the derived list plan.md §7
originally settled on. This lets a user pre-define a module before anything
is actually tagged with it yet, and rename/delete without touching real data
by hand."""

from __future__ import annotations

import json
from pathlib import Path

from src import config

_STORE_PATH = Path(config.PROJECT_ROOT) / "data" / "modules.json"


def _load() -> list[str]:
    if not _STORE_PATH.exists():
        return []
    return json.loads(_STORE_PATH.read_text())


def _save(modules: list[str]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(sorted(set(modules)), indent=2))


def list_manual() -> list[str]:
    return _load()


def add(name: str) -> list[str]:
    name = name.strip()
    if not name:
        raise ValueError("Module name cannot be empty")
    modules = _load()
    if name not in modules:
        modules.append(name)
        _save(modules)
    return _load()


def remove(name: str) -> list[str]:
    _save([m for m in _load() if m != name])
    return _load()


def rename(old: str, new: str) -> list[str]:
    """Renaming always leaves `new` in the manual list afterward — even if
    `old` was only ever a derived (data-only) module, not previously
    manually tracked — so it stays manageable (deletable/renameable) going
    forward."""
    new = new.strip()
    if not new:
        raise ValueError("New module name cannot be empty")
    modules = _load()
    if old in modules:
        modules = [new if m == old else m for m in modules]
    elif new not in modules:
        modules.append(new)
    _save(modules)
    return _load()
