import json

import pytest

from src.generation.generator import parse_test_cases
from src.vectorstore import test_cases_store


def _case(**overrides):
    base = {
        "title": "Login fails with wrong password",
        "description": "Verifies login is rejected when the password is incorrect",
        "preconditions": "User has an active account",
        "steps": ["Enter a valid username", "Enter an incorrect password", "Submit"],
        "expected_result": "An error message is shown and the user is not logged in",
        "category": "Negative",
        "priority": "High",
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def empty_library(monkeypatch):
    # parse_test_cases() mints ids via next_sequence_ids(), which checks the
    # persisted library for the highest existing number — stub it empty so
    # these tests are hermetic and deterministic (start at _001 every time)
    # regardless of what's actually in this machine's chroma_db.
    monkeypatch.setattr(test_cases_store, "list_all", lambda **kwargs: [])


def test_parse_test_cases_builds_expected_fields():
    response = json.dumps([_case()])

    cases = parse_test_cases(response, condition_id="COND-1", trace="PROJ-1, AC-1", module="Auth")

    assert len(cases) == 1
    tc = cases[0]
    assert tc.title == "Login fails with wrong password"
    assert tc.description == "Verifies login is rejected when the password is incorrect"
    assert tc.category == "Negative"
    assert tc.priority == "High"
    assert tc.module == "Auth"
    assert tc.trace == "PROJ-1, AC-1"
    assert tc.condition_id == "COND-1"
    assert tc.source == "generated"
    assert tc.id == "TC_AUTH_001"


def test_parse_test_cases_id_defaults_to_not_defined_without_a_module():
    cases = parse_test_cases(json.dumps([_case()]), condition_id="COND-1")
    assert cases[0].id == "TC_NOT_DEFINED_001"


def test_parse_test_cases_custom_id_prefix_overrides_module_derived_one():
    cases = parse_test_cases(json.dumps([_case(), _case()]), condition_id="COND-1", module="Auth", id_prefix="DEMND002_Reg_TC_")
    assert [c.id for c in cases] == ["DEMND002_Reg_TC_001", "DEMND002_Reg_TC_002"]


def test_parse_test_cases_ids_increment_within_one_batch():
    cases = parse_test_cases(json.dumps([_case(), _case(), _case()]), condition_id="COND-1", module="Payments")
    assert [c.id for c in cases] == ["TC_PAYMENTS_001", "TC_PAYMENTS_002", "TC_PAYMENTS_003"]


def test_parse_test_cases_starts_ungrounded():
    # Fresh generation output must never read as trusted before coverage_auditor runs.
    cases = parse_test_cases(json.dumps([_case()]), condition_id="COND-1")
    assert cases[0].grounded is False


def test_parse_test_cases_ids_are_unique_across_calls_via_existing_ids():
    # Regression (pre-sequential-id scheme): ids used to restart from G1 every
    # call, colliding once two batches for the same condition were merged
    # (see pipeline.py). The sequential scheme relies on the caller passing
    # existing_ids forward — this is pipeline.py's job now, exercised here directly.
    first = parse_test_cases(json.dumps([_case(), _case()]), condition_id="COND-1", module="Auth")
    second = parse_test_cases(
        json.dumps([_case()]), condition_id="COND-1", module="Auth", existing_ids={c.id for c in first}
    )

    all_ids = [c.id for c in first] + [c.id for c in second]
    assert len(all_ids) == len(set(all_ids))
    assert second[0].id == "TC_AUTH_003"


def test_parse_test_cases_skips_invalid_category_without_failing_batch():
    response = json.dumps([_case(category="Not A Real Category"), _case()])

    cases = parse_test_cases(response, condition_id="COND-1")

    assert len(cases) == 1
    assert cases[0].category == "Negative"


def test_parse_test_cases_skips_blank_title():
    response = json.dumps([_case(title=""), _case()])

    cases = parse_test_cases(response, condition_id="COND-1")

    assert len(cases) == 1


def test_parse_test_cases_invalid_priority_defaults_to_medium():
    response = json.dumps([_case(priority="Critical")])

    cases = parse_test_cases(response, condition_id="COND-1")

    assert cases[0].priority == "Medium"


def test_parse_test_cases_strips_markdown_fences():
    response = "```json\n" + json.dumps([_case()]) + "\n```"

    cases = parse_test_cases(response, condition_id="COND-1")

    assert len(cases) == 1


def test_parse_test_cases_rejects_non_list_json():
    with pytest.raises(ValueError):
        parse_test_cases('{"not": "a list"}', condition_id="COND-1")
