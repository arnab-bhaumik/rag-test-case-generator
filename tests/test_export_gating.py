from datetime import datetime, timezone

from api.routers.export import _export_status
from src.models.schemas import Category, CoverageGap, Run, TestCase


def _run(test_cases: list[TestCase], gaps: list[CoverageGap] | None = None) -> Run:
    return Run(
        id="run-1",
        source_type="jira",
        source_id="PROJ-1",
        created_at=datetime.now(timezone.utc).isoformat(),
        test_cases=test_cases,
        gaps=gaps or [],
    )


def _tc(id_: str, status: str, **overrides) -> TestCase:
    base = dict(id=id_, title=f"Case {id_}", status=status)
    base.update(overrides)
    return TestCase(**base)


def test_blocked_when_zero_approved_cases():
    status = _export_status(_run([_tc("TC1", "unreviewed"), _tc("TC2", "rejected")]))
    assert status["blocked"] is True
    assert status["approved_count"] == 0
    assert "0 approved" in status["reason"]


def test_not_blocked_when_at_least_one_approved_even_with_pending_verification():
    # Regression: the original gate blocked export on ANY pending
    # verification anywhere in the run, making large batches (hundreds of
    # cases) impossible to partially ship. Reported in real usage.
    cases = [
        _tc("TC1", "approved"),
        _tc("TC2", "unreviewed", grounded=False, manually_verified=False),
    ]
    status = _export_status(_run(cases))

    assert status["blocked"] is False
    assert status["reason"] is None
    assert status["approved_count"] == 1


def test_note_mentions_pending_verification_when_not_blocked():
    cases = [_tc("TC1", "approved"), _tc("TC2", "unreviewed", grounded=False, manually_verified=False)]
    status = _export_status(_run(cases))

    assert status["note"] is not None
    assert "1 case" in status["note"]
    assert "manual verification" in status["note"]
    assert "1 approved case" in status["note"]


def test_note_mentions_unacknowledged_gaps_when_not_blocked():
    cases = [_tc("TC1", "approved")]
    gaps = [CoverageGap(category=Category.security, acknowledged=False)]
    status = _export_status(_run(cases, gaps))

    assert status["blocked"] is False
    assert "1 coverage gap" in status["note"]


def test_acknowledged_gaps_do_not_appear_in_note():
    cases = [_tc("TC1", "approved")]
    gaps = [CoverageGap(category=Category.security, acknowledged=True)]
    status = _export_status(_run(cases, gaps))

    assert status["note"] is None


def test_grounded_unreviewed_case_does_not_count_as_needing_verification():
    # A case can be unreviewed without needing manual verification — it's
    # only "needs verification" if it's also ungrounded and not yet verified.
    cases = [_tc("TC1", "approved"), _tc("TC2", "unreviewed", grounded=True)]
    status = _export_status(_run(cases))

    assert status["note"] is None


def test_manually_verified_case_does_not_count_as_needing_verification():
    cases = [_tc("TC1", "approved"), _tc("TC2", "unreviewed", grounded=False, manually_verified=True)]
    status = _export_status(_run(cases))

    assert status["note"] is None


def test_rejected_ungrounded_case_does_not_count_as_needing_verification():
    # Rejecting is itself a resolution — it shouldn't keep blocking/nagging.
    cases = [_tc("TC1", "approved"), _tc("TC2", "rejected", grounded=False, manually_verified=False)]
    status = _export_status(_run(cases))

    assert status["note"] is None


def test_no_note_when_fully_resolved():
    cases = [_tc("TC1", "approved"), _tc("TC2", "approved")]
    status = _export_status(_run(cases))

    assert status["blocked"] is False
    assert status["note"] is None
