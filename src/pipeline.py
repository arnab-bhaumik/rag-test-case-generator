"""Orchestrates the full end-to-end flow for one run: ingest -> decompose ->
(per condition) retrieve context -> generate -> audit + gap-fill -> aggregate
run-level coverage gaps.

Runs are tracked in-process (a module-level dict), not in a database or task
queue — an intentional MVP simplification (see plan.md §3/§7): run history is
lost on restart, and this only scales to a single API process. Revisit if/when
real ticket volume or multi-process deployment demands it.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from src.generation.coverage_auditor import audit_grounding, find_gaps, regenerate_gaps
from src.generation.decomposer import decompose
from src.generation.generator import generate_test_cases, generate_test_cases_for_categories
from src.ingestion.chunker import chunk_sections, chunk_text
from src.ingestion.doc_parser import parse_document
from src.ingestion.jira_client import JiraClient
from src.models.schemas import Category, Condition, CoverageGap, Run, RunStep, RunStepStatus, TestCase
from src.retrieval.retriever import RetrievedContext, retrieve_context
from src.vectorstore.design_docs_store import upsert as upsert_design_docs

logger = logging.getLogger(__name__)

STEP_NAMES = [
    "Decomposing requirement",
    "Retrieving related context",
    "Generating test cases",
    "Checking coverage",
]

RUNS: dict[str, Run] = {}


def new_run(source_type: str, source_id: str, module: str | None, scope: str | None = None, id_prefix: str | None = None) -> Run:
    run = Run(
        id=str(uuid.uuid4()),
        source_type=source_type,
        source_id=source_id,
        module=module,
        scope=scope,
        id_prefix=id_prefix,
        status=RunStepStatus.in_progress,
        steps=[RunStep(name=name) for name in STEP_NAMES],
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    RUNS[run.id] = run
    return run


def _set_step(run: Run, name: str, status: RunStepStatus) -> None:
    for step in run.steps:
        if step.name == name:
            step.status = status
            return


def _set_step_progress(run: Run, name: str, current: int, total: int) -> None:
    """Only meaningful for steps that loop per-condition (generation, coverage
    checking) — decomposition is one LLM call for the whole run, and retrieval
    is local/near-instant, so neither reports progress (total stays 0)."""
    for step in run.steps:
        if step.name == name:
            step.current = current
            step.total = total
            return


def _ingest(run: Run, doc_path: str | None) -> str:
    """Fetches/parses the source, chunks it into design_docs for retrieval,
    and returns the flat requirement text decomposer.py works from."""
    if run.source_type == "jira":
        content = JiraClient().get_issue_content(run.source_id)
        text = "\n\n".join(filter(None, [content["description"], *content["comments"]]))
        chunks = chunk_text(text, source_type="jira", source_id=run.source_id, module=run.module)
    else:
        sections = parse_document(doc_path)
        text = "\n\n".join(s.text for s in sections)
        chunks = chunk_sections(sections, source_type="doc", source_id=run.source_id, module=run.module)

    upsert_design_docs(chunks)
    return text


def _trace_for(source_id: str, condition: Condition) -> str:
    return f"{source_id}, {condition.ac_ref}" if condition.ac_ref else source_id


def execute_run(run_id: str, doc_path: str | None = None) -> None:
    """The actual pipeline work — called as a FastAPI background task so
    POST /runs can return immediately with a run_id to poll.

    Ingestion/decomposition failures fail the whole run (nothing downstream
    is possible without conditions). Per-condition generation/audit failures
    do not — each condition is isolated in its own try/except below, so one
    bad LLM response degrades that condition to zero cases (a natural gap)
    rather than discarding every other condition's successfully generated
    work. LLM/Jira calls already get 3 retry attempts each (llm_client.py/
    jira_client.py) before an exception reaches here at all."""
    run = RUNS[run_id]
    try:
        # Marked in_progress before ingestion (not after) so the UI shows
        # immediate feedback instead of every step reading "pending" during
        # the Jira/doc fetch — ingestion has no dedicated step of its own
        # (plan.md §5 step 2), so it's bundled into "Decomposing requirement".
        _set_step(run, "Decomposing requirement", RunStepStatus.in_progress)
        run.requirement_text = _ingest(run, doc_path)

        conditions = decompose(run.requirement_text, requirement_id=run.source_id, scope=run.scope)
        run.conditions = conditions
        logger.info("Run %s: decomposed into %d conditions", run_id, len(conditions))
        _set_step(run, "Decomposing requirement", RunStepStatus.done)

        _set_step(run, "Retrieving related context", RunStepStatus.in_progress)
        contexts: dict[str, RetrievedContext] = {
            c.id: retrieve_context(c.text, module=run.module) for c in conditions
        }
        _set_step(run, "Retrieving related context", RunStepStatus.done)

        _set_step(run, "Generating test cases", RunStepStatus.in_progress)
        _set_step_progress(run, "Generating test cases", 0, len(conditions))
        generated: dict[str, list[TestCase]] = {}
        # Tracks every id already in play — cases aren't written into the
        # library (and thus don't influence next_sequence_ids()) until
        # approved, so without this, sequential numbering could hand out the
        # same TC_{MODULE}_### id to two different not-yet-approved siblings,
        # including ones sitting unapproved in a *different* run — seeded from
        # every run currently in memory, not just this one.
        minted_ids: set[str] = {tc.id for r in RUNS.values() for tc in r.test_cases}
        for i, condition in enumerate(conditions):
            try:
                cases = generate_test_cases(
                    condition.text,
                    condition.id,
                    contexts[condition.id],
                    trace=_trace_for(run.source_id, condition),
                    module=run.module,
                    existing_ids=minted_ids,
                    id_prefix=run.id_prefix,
                )
                minted_ids.update(tc.id for tc in cases)
                generated[condition.id] = cases
            except Exception:
                logger.error("Run %s: generation failed for condition %s", run_id, condition.id, exc_info=True)
                generated[condition.id] = []
            _set_step_progress(run, "Generating test cases", i + 1, len(conditions))
        _set_step(run, "Generating test cases", RunStepStatus.done)

        _set_step(run, "Checking coverage", RunStepStatus.in_progress)
        _set_step_progress(run, "Checking coverage", 0, len(conditions))
        all_cases: list[TestCase] = []
        for i, condition in enumerate(conditions):
            try:
                cases = audit_grounding(generated[condition.id], run.requirement_text)
                per_condition_gaps = find_gaps(cases)
                if per_condition_gaps:
                    filled = regenerate_gaps(
                        condition.text,
                        condition.id,
                        contexts[condition.id],
                        per_condition_gaps,
                        trace=_trace_for(run.source_id, condition),
                        module=run.module,
                        existing_ids=minted_ids,
                        id_prefix=run.id_prefix,
                    )
                    minted_ids.update(tc.id for tc in filled)
                    cases = cases + filled
                all_cases.extend(cases)
            except Exception:
                logger.error("Run %s: coverage check failed for condition %s", run_id, condition.id, exc_info=True)
                all_cases.extend(generated[condition.id])  # keep the ungrounded originals rather than losing them
            _set_step_progress(run, "Checking coverage", i + 1, len(conditions))

        run.test_cases = all_cases
        run.gaps = [CoverageGap(category=c) for c in find_gaps(all_cases)]
        _set_step(run, "Checking coverage", RunStepStatus.done)

        run.status = RunStepStatus.done
        logger.info("Run %s: done — %d test cases, %d gaps", run_id, len(all_cases), len(run.gaps))
    except Exception as e:
        logger.error("Run %s: failed", run_id, exc_info=True)
        run.status = RunStepStatus.failed
        run.error = str(e)
        raise


def fill_gap_category(run: Run, category: Category) -> list[TestCase]:
    """Screen 2's "Generate manually" gap action. A run-level gap means every
    condition's per-condition regenerate_gaps() already tried this category
    and came up empty (see execute_run) — so this re-tries against every
    condition once more (models are non-deterministic) rather than assuming
    it's hopeless. May still legitimately return nothing."""
    new_cases: list[TestCase] = []
    minted_ids: set[str] = {tc.id for r in RUNS.values() for tc in r.test_cases}
    for condition in run.conditions:
        try:
            ctx = retrieve_context(condition.text, module=run.module)
            cases = generate_test_cases_for_categories(
                condition.text,
                condition.id,
                ctx,
                categories=[category.value],
                trace=_trace_for(run.source_id, condition),
                module=run.module,
                existing_ids=minted_ids,
                id_prefix=run.id_prefix,
            )
            if cases:
                audited = audit_grounding(cases, run.requirement_text)
                new_cases.extend(audited)
                minted_ids.update(tc.id for tc in audited)
        except Exception:
            # Same resilience principle as execute_run: one condition's LLM
            # failure (rate limit, transient error) shouldn't discard whatever
            # the other conditions already produced for this gap-fill attempt.
            logger.error("fill_gap_category: generation failed for condition %s", condition.id, exc_info=True)

    if new_cases:
        run.test_cases.extend(new_cases)
        run.gaps = [g for g in run.gaps if g.category != category]

    return new_cases
