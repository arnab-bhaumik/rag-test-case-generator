import json

import pytest

from src.generation.coverage_auditor import find_gaps, parse_audit_results
from src.models.schemas import Category, TestCase


def _tc(category: str, **overrides) -> TestCase:
    base = dict(id="C1::G1", title="Some case", category=category, grounded=False)
    base.update(overrides)
    return TestCase(**base)


def test_find_gaps_returns_all_categories_when_no_cases():
    assert find_gaps([]) == list(Category)


def test_find_gaps_returns_only_missing_categories():
    cases = [_tc("Positive"), _tc("Negative"), _tc("Boundary")]

    gaps = find_gaps(cases)

    assert Category.positive not in gaps
    assert Category.negative not in gaps
    assert Category.boundary not in gaps
    assert Category.security in gaps
    assert Category.edge in gaps
    assert len(gaps) == len(Category) - 3


def test_find_gaps_empty_when_all_categories_present():
    cases = [_tc(c.value) for c in Category]
    assert find_gaps(cases) == []


def test_find_gaps_preserves_category_enum_order():
    # UX Screen/Screen2-ReviewQueue.dc.html's CATEGORY_ORDER depends on this.
    gaps = find_gaps([])
    assert gaps == list(Category)


def test_parse_audit_results_applies_grounded_flag_in_order():
    cases = [_tc("Positive", id="C1::G1"), _tc("Negative", id="C1::G2")]
    response = json.dumps([{"grounded": True, "reason": "matches AC-1"}, {"grounded": False, "reason": "not stated"}])

    audited = parse_audit_results(response, cases)

    assert audited[0].id == "C1::G1"
    assert audited[0].grounded is True
    assert audited[1].id == "C1::G2"
    assert audited[1].grounded is False


def test_parse_audit_results_does_not_mutate_input_cases():
    cases = [_tc("Positive")]
    response = json.dumps([{"grounded": True, "reason": "ok"}])

    parse_audit_results(response, cases)

    assert cases[0].grounded is False  # original list untouched — model_copy, not in-place mutation


def test_parse_audit_results_missing_grounded_key_defaults_false():
    cases = [_tc("Positive")]
    response = json.dumps([{"reason": "no grounded key at all"}])

    audited = parse_audit_results(response, cases)

    assert audited[0].grounded is False


def test_parse_audit_results_rejects_mismatched_length():
    cases = [_tc("Positive"), _tc("Negative")]
    response = json.dumps([{"grounded": True, "reason": "only one result for two cases"}])

    with pytest.raises(ValueError):
        parse_audit_results(response, cases)


def test_parse_audit_results_strips_markdown_fences():
    cases = [_tc("Positive")]
    response = '```json\n[{"grounded": true, "reason": "ok"}]\n```'

    audited = parse_audit_results(response, cases)

    assert audited[0].grounded is True
