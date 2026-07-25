import requests

from src.ingestion.jira_client import _is_transient_http_error, adf_to_text, extract_acceptance_criteria


def test_adf_to_text_flattens_paragraph():
    node = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hello world."}]}]}
    assert adf_to_text(node).strip() == "Hello world."


def test_adf_to_text_flattens_bullet_list():
    node = {
        "type": "bulletList",
        "content": [
            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "First item"}]}]},
            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Second item"}]}]},
        ],
    }
    text = adf_to_text(node)
    assert "- First item" in text
    assert "- Second item" in text


def test_adf_to_text_handles_none():
    assert adf_to_text(None) == ""


def test_adf_to_text_handles_hard_break():
    node = {"type": "paragraph", "content": [{"type": "text", "text": "Line one"}, {"type": "hardBreak"}, {"type": "text", "text": "Line two"}]}
    text = adf_to_text(node)
    assert "Line one\nLine two" in text


def test_extract_acceptance_criteria_finds_heading():
    text = "Some description.\n\nAcceptance Criteria\nMust do X.\nMust do Y."
    ac = extract_acceptance_criteria(text)
    assert ac == "Must do X.\nMust do Y."


def test_extract_acceptance_criteria_case_insensitive_and_with_colon():
    text = "Description.\nACCEPTANCE CRITERIA:\nDetail here."
    assert extract_acceptance_criteria(text) == "Detail here."


def test_extract_acceptance_criteria_returns_none_when_absent():
    assert extract_acceptance_criteria("Just a plain description with no AC section.") is None


def test_extract_acceptance_criteria_returns_none_when_heading_is_last_line():
    assert extract_acceptance_criteria("Some text.\nAcceptance Criteria") is None


def _response(status_code: int) -> requests.Response:
    r = requests.Response()
    r.status_code = status_code
    return r


def test_is_transient_http_error_retries_rate_limit():
    exc = requests.HTTPError(response=_response(429))
    assert _is_transient_http_error(exc) is True


def test_is_transient_http_error_retries_server_errors():
    for status in (500, 502, 503, 504):
        assert _is_transient_http_error(requests.HTTPError(response=_response(status))) is True


def test_is_transient_http_error_does_not_retry_client_errors():
    for status in (400, 401, 403, 404):
        assert _is_transient_http_error(requests.HTTPError(response=_response(status))) is False


def test_is_transient_http_error_retries_connection_and_timeout():
    assert _is_transient_http_error(requests.ConnectionError()) is True
    assert _is_transient_http_error(requests.Timeout()) is True


def test_is_transient_http_error_ignores_unrelated_exceptions():
    assert _is_transient_http_error(ValueError("not a request error")) is False
