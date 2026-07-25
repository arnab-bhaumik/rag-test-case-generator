import requests

from src.export import jira_uploader
from src.export.jira_uploader import _description_adf, _extract_error, upload_test_case
from src.models.schemas import TestCase


class FakeJiraClient:
    """Stands in for JiraClient without needing real Jira credentials in the
    test environment — upload_test_case only touches base_url/auth/headers."""

    base_url = "https://example.atlassian.net"
    auth = None
    headers = {"Accept": "application/json"}


def _tc(**overrides) -> TestCase:
    base = dict(
        id="C1::G1",
        title="Login fails with wrong password",
        preconditions="User has an active account",
        steps=["Enter valid username", "Enter wrong password"],
        expected_result="Login is rejected",
    )
    base.update(overrides)
    return TestCase(**base)


def _fake_response(status_code: int, json_body: dict | None = None) -> requests.Response:
    r = requests.Response()
    r.status_code = status_code
    if json_body is not None:
        import json

        r._content = json.dumps(json_body).encode()
    return r


def test_description_adf_includes_preconditions_steps_and_expected_result():
    tc = _tc()
    adf = _description_adf(tc)

    text_blob = str(adf)
    assert "User has an active account" in text_blob
    assert "Enter valid username" in text_blob
    assert "Enter wrong password" in text_blob
    assert "Login is rejected" in text_blob
    assert adf["type"] == "doc"


def test_description_adf_handles_empty_fields_gracefully():
    tc = _tc(preconditions="", steps=[], expected_result="")
    adf = _description_adf(tc)

    # still valid ADF (at least one content node) even with nothing to say
    assert adf["type"] == "doc"
    assert len(adf["content"]) >= 1


def test_extract_error_reads_error_messages():
    response = _fake_response(400, {"errorMessages": ["Field 'summary' is required"], "errors": {}})
    assert "Field 'summary' is required" in _extract_error(response)


def test_extract_error_reads_field_errors():
    response = _fake_response(400, {"errorMessages": [], "errors": {"issuetype": "invalid issue type"}})
    assert "issuetype: invalid issue type" in _extract_error(response)


def test_extract_error_falls_back_to_status_code_when_no_body():
    response = _fake_response(500)
    response._content = b"not json"
    assert _extract_error(response) == "HTTP 500"


def test_upload_test_case_success(monkeypatch):
    tc = _tc()
    fake_response = _fake_response(201, {"key": "PROJ-42"})
    monkeypatch.setattr(jira_uploader, "_post_issue", lambda client, payload: fake_response)
    monkeypatch.setattr(jira_uploader, "_link_to_source", lambda *a, **k: None)

    result = upload_test_case(FakeJiraClient(), "PROJ", tc, source_ticket_key="PROJ-1")

    assert result["success"] is True
    assert result["jira_key"] == "PROJ-42"
    assert result["jira_url"] == "https://example.atlassian.net/browse/PROJ-42"
    assert result["reason"] is None
    assert result["test_case_id"] == tc.id


def test_upload_test_case_http_failure_returns_structured_result(monkeypatch):
    tc = _tc()
    error_response = _fake_response(400, {"errorMessages": ["Bad request"], "errors": {}})

    def raise_http_error(client, payload):
        raise requests.HTTPError(response=error_response)

    monkeypatch.setattr(jira_uploader, "_post_issue", raise_http_error)

    result = upload_test_case(FakeJiraClient(), "PROJ", tc, source_ticket_key=None)

    assert result["success"] is False
    assert result["jira_key"] is None
    assert "Bad request" in result["reason"]


def test_upload_test_case_does_not_link_when_no_source_ticket(monkeypatch):
    tc = _tc()
    fake_response = _fake_response(201, {"key": "PROJ-42"})
    link_calls = []
    monkeypatch.setattr(jira_uploader, "_post_issue", lambda client, payload: fake_response)
    monkeypatch.setattr(jira_uploader, "_link_to_source", lambda *a, **k: link_calls.append(a))

    upload_test_case(FakeJiraClient(), "PROJ", tc, source_ticket_key=None)

    assert link_calls == []


def test_upload_test_case_network_failure_returns_structured_result(monkeypatch):
    tc = _tc()

    def raise_connection_error(client, payload):
        raise requests.ConnectionError("could not connect")

    monkeypatch.setattr(jira_uploader, "_post_issue", raise_connection_error)

    result = upload_test_case(FakeJiraClient(), "PROJ", tc, source_ticket_key=None)

    assert result["success"] is False
    assert "could not connect" in result["reason"]
