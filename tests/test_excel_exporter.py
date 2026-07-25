from datetime import datetime, timezone

from src.export.excel_exporter import build_workbook
from src.models.schemas import Condition, Run, TestCase


def _run(test_cases: list[TestCase], conditions: list[Condition] | None = None) -> Run:
    return Run(
        id="run-1",
        source_type="jira",
        source_id="PROJ-1",
        module="Auth",
        created_at=datetime.now(timezone.utc).isoformat(),
        conditions=conditions or [],
        test_cases=test_cases,
    )


def _tc(id_: str, status: str, **overrides) -> TestCase:
    base = dict(
        id=id_,
        title=f"Case {id_}",
        preconditions="Some precondition",
        steps=["Step one", "Step two"],
        expected_result="Expected outcome",
        category="Positive",
        priority="High",
        status=status,
        trace="PROJ-1, AC-1",
    )
    base.update(overrides)
    return TestCase(**base)


def test_build_workbook_has_both_sheets():
    wb = build_workbook(_run([]))
    assert wb.sheetnames == ["Test Cases", "RTM"]


def test_build_workbook_only_includes_approved_cases():
    cases = [_tc("TC1", "approved"), _tc("TC2", "rejected"), _tc("TC3", "unreviewed")]

    wb = build_workbook(_run(cases))
    ws = wb["Test Cases"]

    # header row + exactly one data row (only the approved case)
    assert ws.max_row == 2
    assert ws.cell(row=2, column=1).value == "TC1"


def test_build_workbook_header_row_matches_expected_columns():
    wb = build_workbook(_run([]))
    ws = wb["Test Cases"]
    header = [ws.cell(row=1, column=i).value for i in range(1, 13)]

    assert header == [
        "Test Case ID",
        "Test Scenario",
        "Description",
        "Category",
        "Priority",
        "Module",
        "Pre-conditions",
        "Steps",
        "Expected Results",
        "Trace",
        "Status",
        "Jira Key",
    ]


def test_build_workbook_steps_are_numbered_and_joined():
    cases = [_tc("TC1", "approved", steps=["First step", "Second step"])]

    wb = build_workbook(_run(cases))
    ws = wb["Test Cases"]

    assert ws.cell(row=2, column=8).value == "1. First step\n2. Second step"


def test_build_workbook_rtm_sheet_reflects_conditions():
    condition = Condition(id="C1", requirement_id="PROJ-1", text="Login succeeds with valid credentials", ac_ref="AC-1")
    cases = [_tc("TC1", "approved", condition_id="C1")]

    wb = build_workbook(_run(cases, conditions=[condition]))
    ws = wb["RTM"]

    assert ws.cell(row=2, column=1).value == "AC-1"
    assert ws.cell(row=2, column=2).value == "Login succeeds with valid credentials"
    assert ws.cell(row=2, column=3).value == "TC1"
    assert ws.cell(row=2, column=4).value == "Covered"


def test_build_workbook_jira_key_column_populated_when_set():
    cases = [_tc("TC1", "approved", jira_key="PROJ-99")]

    wb = build_workbook(_run(cases))
    ws = wb["Test Cases"]

    assert ws.cell(row=2, column=12).value == "PROJ-99"
