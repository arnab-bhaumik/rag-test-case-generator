from src.models.schemas import Condition, TestCase
from src.traceability.rtm_builder import build_rtm


def _condition(id_: str, ac_ref: str | None = None) -> Condition:
    return Condition(id=id_, requirement_id="PROJ-1", text=f"Condition {id_}", ac_ref=ac_ref)


def _tc(id_: str, condition_id: str, status: str = "unreviewed") -> TestCase:
    return TestCase(id=id_, title=f"Case {id_}", condition_id=condition_id, status=status)


def test_build_rtm_one_row_per_condition_in_order():
    conditions = [_condition("C1"), _condition("C2"), _condition("C3")]

    rows = build_rtm(conditions, [])

    assert [r.condition_id for r in rows] == ["C1", "C2", "C3"]


def test_build_rtm_links_test_cases_by_condition_id():
    conditions = [_condition("C1"), _condition("C2")]
    cases = [_tc("TC1", "C1"), _tc("TC2", "C1"), _tc("TC3", "C2")]

    rows = build_rtm(conditions, cases)

    assert rows[0].linked_test_case_ids == ["TC1", "TC2"]
    assert rows[1].linked_test_case_ids == ["TC3"]


def test_build_rtm_ignores_cases_with_no_condition_id():
    conditions = [_condition("C1")]
    cases = [_tc("TC1", "C1"), TestCase(id="ORPHAN", title="No condition link", condition_id=None)]

    rows = build_rtm(conditions, cases)

    assert rows[0].linked_test_case_ids == ["TC1"]


def test_build_rtm_covered_only_when_a_linked_case_is_approved():
    conditions = [_condition("C1"), _condition("C2"), _condition("C3")]
    cases = [
        _tc("TC1", "C1", status="approved"),
        _tc("TC2", "C2", status="unreviewed"),
        _tc("TC3", "C3", status="rejected"),
    ]

    rows = build_rtm(conditions, cases)

    assert rows[0].covered is True  # has an approved case
    assert rows[1].covered is False  # only unreviewed
    assert rows[2].covered is False  # only rejected


def test_build_rtm_uncovered_when_no_linked_cases():
    conditions = [_condition("C1")]

    rows = build_rtm(conditions, [])

    assert rows[0].linked_test_case_ids == []
    assert rows[0].covered is False


def test_build_rtm_preserves_ac_ref():
    conditions = [_condition("C1", ac_ref="AC-2"), _condition("C2", ac_ref=None)]

    rows = build_rtm(conditions, [])

    assert rows[0].ac_ref == "AC-2"
    assert rows[1].ac_ref is None
