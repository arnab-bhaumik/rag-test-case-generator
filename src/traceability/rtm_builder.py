"""Builds the Requirement Traceability Matrix: each condition mapped to its
linked test cases and whether it's covered — the data Screen 3 (Coverage
Matrix) renders."""

from __future__ import annotations

from pydantic import BaseModel

from src.models.schemas import Condition, ReviewStatus, TestCase


class RTMRow(BaseModel):
    condition_id: str
    ac_ref: str | None
    condition_text: str
    linked_test_case_ids: list[str]
    covered: bool  # True if at least one linked case is approved — matches
    # UX Screen/Screen3-TestCaseLibrary.dc.html's `covered = links.some(l => l.status === 'approved')`


def build_rtm(conditions: list[Condition], test_cases: list[TestCase]) -> list[RTMRow]:
    by_condition: dict[str, list[TestCase]] = {}
    for tc in test_cases:
        if tc.condition_id:
            by_condition.setdefault(tc.condition_id, []).append(tc)

    rows = []
    for condition in conditions:
        linked = by_condition.get(condition.id, [])
        rows.append(
            RTMRow(
                condition_id=condition.id,
                ac_ref=condition.ac_ref,
                condition_text=condition.text,
                linked_test_case_ids=[tc.id for tc in linked],
                covered=any(tc.status == ReviewStatus.approved for tc in linked),
            )
        )
    return rows
