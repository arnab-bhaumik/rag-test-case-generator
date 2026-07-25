"""Pydantic models shared across the pipeline."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    positive = "Positive"
    negative = "Negative"
    boundary = "Boundary"
    edge = "Edge"
    security = "Security"
    integration = "Integration"
    data_validation = "Data Validation"


class Priority(str, Enum):
    high = "High"
    medium = "Medium"
    low = "Low"


class ReviewStatus(str, Enum):
    unreviewed = "unreviewed"
    approved = "approved"
    rejected = "rejected"


class TestCase(BaseModel):
    id: str
    title: str  # shown in the UI as "Test Scenario"
    description: str = ""  # one-line test objective — what this case verifies and why
    preconditions: str = ""
    steps: list[str] = Field(default_factory=list)
    expected_result: str = ""
    module: str | None = None
    priority: Priority = Priority.medium
    category: Category | None = None
    source: str = "library"  # "library" (imported old test case) | "generated"
    trace: str | None = None  # e.g. "PROJ-4821, AC-1" — set for generated cases
    status: ReviewStatus = ReviewStatus.unreviewed
    grounded: bool = True  # library cases are trusted by default; generated cases get this from coverage_auditor
    manually_verified: bool = False
    edited: bool = False
    condition_id: str | None = None  # set for generated cases; links back to the Condition it was generated for
    jira_key: str | None = None  # set once uploaded (Sprint 8) — lets "upload" skip already-uploaded cases
    # Library grouping (Test Case Library screen) — set when a case enters old_test_cases, either via
    # a file import (one session per upload) or via bulk-approve write-back (one session per run).
    # None for anything not yet in the library, and for pre-existing library entries from before this field.
    session_id: str | None = None
    session_label: str | None = None  # e.g. "old_tests.csv" or "SCRUM-8"
    session_created_at: str | None = None  # ISO 8601


class Requirement(BaseModel):
    id: str  # e.g. a Jira key or a doc's source_id (see chunker.Chunk.source_id)
    source_type: str  # "jira" | "doc"
    text: str  # combined raw text (summary+description+AC for Jira; concatenated sections for a doc)
    module: str | None = None


class Condition(BaseModel):
    id: str
    requirement_id: str
    text: str  # one atomic testable behavior, e.g. "Refund is rejected for orders older than 30 days"
    ac_ref: str | None = None  # e.g. "AC-2" if traceable to a specific acceptance criterion
    order: int = 0


class RunStepStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    failed = "failed"


class RunStep(BaseModel):
    name: str  # e.g. "Decomposing requirement" — see pipeline.STEP_NAMES
    status: RunStepStatus = RunStepStatus.pending
    current: int = 0  # conditions processed so far — only meaningful when total > 0
    total: int = 0  # 0 means this step isn't divisible (e.g. decomposition is one LLM call, not per-condition)


class CoverageGap(BaseModel):
    category: Category
    acknowledged: bool = False


class Run(BaseModel):
    id: str
    source_type: str  # "jira" | "doc"
    source_id: str  # ticket key, or the uploaded doc's filename stem
    module: str | None = None
    scope: str | None = None  # optional user-provided focus — see decomposer.build_user_prompt()
    id_prefix: str | None = None  # optional user-provided test case id prefix — see test_cases_store.next_sequence_ids()
    status: RunStepStatus = RunStepStatus.pending
    steps: list[RunStep] = Field(default_factory=list)
    error: str | None = None
    created_at: str  # ISO 8601
    requirement_text: str = ""  # persisted so single-case regenerate/audit doesn't need to re-fetch Jira/doc
    conditions: list[Condition] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list)
    gaps: list[CoverageGap] = Field(default_factory=list)
