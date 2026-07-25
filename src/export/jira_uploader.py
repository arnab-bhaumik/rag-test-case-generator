"""Creates Jira "Test Case" issues from approved TestCases, linked back to
the source ticket.

plan.md §7's open decision (plain issue type vs. a plugin's, e.g. Xray
"Test") is resolved by what's actually configured on the connected Jira
instance: it already has a purpose-built "Test Case" issue type (confirmed
live via /createmeta, not guessed), so no Xray/plugin fallback is needed."""

from __future__ import annotations

import logging

import requests

from src import config
from src.ingestion.jira_client import JiraClient, jira_http_retry
from src.models.schemas import TestCase

logger = logging.getLogger(__name__)

ISSUE_TYPE_NAME = "Test Case"
LINK_TYPE_NAME = "Relates"


def _description_adf(tc: TestCase) -> dict:
    content: list[dict] = []
    if tc.preconditions:
        content.append({"type": "paragraph", "content": [{"type": "text", "text": f"Preconditions: {tc.preconditions}"}]})
    if tc.steps:
        content.append({"type": "paragraph", "content": [{"type": "text", "text": "Steps:"}]})
        content.append(
            {
                "type": "orderedList",
                "content": [
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": step}]}]}
                    for step in tc.steps
                ],
            }
        )
    if tc.expected_result:
        content.append({"type": "paragraph", "content": [{"type": "text", "text": f"Expected Result: {tc.expected_result}"}]})
    return {"type": "doc", "version": 1, "content": content or [{"type": "paragraph", "content": []}]}


def _extract_error(response: requests.Response) -> str:
    try:
        data = response.json()
        parts = list(data.get("errorMessages") or [])
        parts += [f"{field}: {msg}" for field, msg in (data.get("errors") or {}).items()]
        return "; ".join(parts) or f"HTTP {response.status_code}"
    except ValueError:
        return f"HTTP {response.status_code}"


@jira_http_retry
def _post_issue(client: JiraClient, payload: dict) -> requests.Response:
    response = requests.post(
        f"{client.base_url}/rest/api/3/issue",
        headers={**client.headers, "Content-Type": "application/json"},
        auth=client.auth,
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response


def _link_to_source(client: JiraClient, new_key: str, source_key: str) -> None:
    """Best-effort — a failed link shouldn't fail the whole upload, the issue
    already exists at this point. Still retried before being given up on."""
    try:
        _retryable_link(client, new_key, source_key)
    except requests.RequestException:
        logger.warning("Could not link %s to %s after retries", new_key, source_key)


@jira_http_retry
def _retryable_link(client: JiraClient, new_key: str, source_key: str) -> None:
    requests.post(
        f"{client.base_url}/rest/api/3/issueLink",
        headers={**client.headers, "Content-Type": "application/json"},
        auth=client.auth,
        json={"type": {"name": LINK_TYPE_NAME}, "inwardIssue": {"key": new_key}, "outwardIssue": {"key": source_key}},
        timeout=15,
    ).raise_for_status()


def upload_test_case(client: JiraClient, project_key: str, tc: TestCase, source_ticket_key: str | None) -> dict:
    """Creates one Jira "Test Case" issue. Returns
    {"test_case_id", "success", "jira_key", "jira_url", "reason"}."""
    payload = {
        "fields": {
            "project": {"key": project_key},
            "issuetype": {"name": ISSUE_TYPE_NAME},
            "summary": tc.title,
            "description": _description_adf(tc),
            "labels": ["generated-test-case"],
        }
    }
    try:
        response = _post_issue(client, payload)
    except requests.HTTPError as e:
        logger.warning("Jira upload failed for %s: %s", tc.id, _extract_error(e.response))
        return {"test_case_id": tc.id, "success": False, "jira_key": None, "jira_url": None, "reason": _extract_error(e.response)}
    except requests.RequestException as e:
        logger.warning("Jira upload failed for %s: %s", tc.id, e)
        return {"test_case_id": tc.id, "success": False, "jira_key": None, "jira_url": None, "reason": str(e)}

    new_key = response.json()["key"]
    if source_ticket_key:
        _link_to_source(client, new_key, source_ticket_key)

    return {
        "test_case_id": tc.id,
        "success": True,
        "jira_key": new_key,
        "jira_url": f"{client.base_url}/browse/{new_key}",
        "reason": None,
    }


def upload_test_cases(test_cases: list[TestCase], source_ticket_key: str | None) -> list[dict]:
    """source_ticket_key both supplies the target project (Jira-sourced runs
    upload into that ticket's own project) and the issue to link new Test
    Case issues back to. Doc-sourced runs have no ticket, so fall back to
    JIRA_PROJECT_KEY with no back-link."""
    project_key = source_ticket_key.split("-")[0] if source_ticket_key else config.require(config.JIRA_PROJECT_KEY, "JIRA_PROJECT_KEY")
    client = JiraClient()
    return [upload_test_case(client, project_key, tc, source_ticket_key) for tc in test_cases]
