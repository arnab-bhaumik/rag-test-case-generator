import json

import pytest

from src.generation.decomposer import build_user_prompt, parse_conditions


def test_build_user_prompt_includes_requirement_text():
    prompt = build_user_prompt("  Users can reset their password.  ")

    assert "Users can reset their password." in prompt
    assert "JSON array" in prompt
    # the raw text is trimmed before being embedded
    assert "  Users can reset their password.  " not in prompt


def test_build_user_prompt_without_scope_has_no_focus_instruction():
    prompt = build_user_prompt("Full requirement text.")
    assert "Focus ONLY" not in prompt


def test_build_user_prompt_with_scope_includes_focus_instruction():
    prompt = build_user_prompt("Full requirement text covering many behaviors.", scope="the retry limit change")

    assert "Focus ONLY" in prompt
    assert "the retry limit change" in prompt
    assert "Full requirement text covering many behaviors." in prompt


def test_build_user_prompt_blank_scope_treated_as_no_scope():
    prompt = build_user_prompt("Full requirement text.", scope="   ")
    assert "Focus ONLY" not in prompt


def test_parse_conditions_builds_ids_and_order():
    response = json.dumps(
        [
            {"text": "Reset link expires after 30 minutes.", "ac_ref": "AC-1"},
            {"text": "Reset link can only be used once.", "ac_ref": None},
        ]
    )

    conditions = parse_conditions(response, requirement_id="PROJ-1")

    assert [c.id for c in conditions] == ["PROJ-1::C1", "PROJ-1::C2"]
    assert [c.order for c in conditions] == [0, 1]
    assert conditions[0].ac_ref == "AC-1"
    assert conditions[1].ac_ref is None
    assert all(c.requirement_id == "PROJ-1" for c in conditions)


def test_parse_conditions_strips_markdown_code_fences():
    response = '```json\n[{"text": "Some condition", "ac_ref": null}]\n```'

    conditions = parse_conditions(response, requirement_id="PROJ-1")

    assert len(conditions) == 1
    assert conditions[0].text == "Some condition"


def test_parse_conditions_skips_blank_text_entries():
    response = json.dumps([{"text": "  ", "ac_ref": None}, {"text": "Real condition", "ac_ref": None}])

    conditions = parse_conditions(response, requirement_id="PROJ-1")

    assert len(conditions) == 1
    assert conditions[0].text == "Real condition"


def test_parse_conditions_missing_ac_ref_key_defaults_to_none():
    response = json.dumps([{"text": "No ac_ref key at all"}])

    conditions = parse_conditions(response, requirement_id="PROJ-1")

    assert conditions[0].ac_ref is None


def test_parse_conditions_rejects_non_list_json():
    with pytest.raises(ValueError):
        parse_conditions('{"not": "a list"}', requirement_id="PROJ-1")


def test_parse_conditions_rejects_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        parse_conditions("this is not json", requirement_id="PROJ-1")
