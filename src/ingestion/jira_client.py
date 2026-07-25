"""Thin wrapper around the Jira REST API v3 for fetching issue content."""

from __future__ import annotations

import logging
import re

import requests
from requests.auth import HTTPBasicAuth
from tenacity import before_sleep_log, retry, retry_if_exception, stop_after_attempt, wait_exponential

from src import config

logger = logging.getLogger(__name__)

_AC_HEADING_RE = re.compile(r"^\s*acceptance criteria\s*:?\s*$", re.IGNORECASE)


def _is_transient_http_error(exc: BaseException) -> bool:
    """Retries connection issues, timeouts, rate limits (429), and server
    errors (5xx) — not 4xx client errors like a bad ticket key or auth
    failure, which won't succeed on retry."""
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


# Shared by jira_uploader.py too — one retry policy for every Jira HTTP call.
jira_http_retry = retry(
    retry=retry_if_exception(_is_transient_http_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def adf_to_text(node: dict | None) -> str:
    """Flattens an Atlassian Document Format node (Jira Cloud's rich-text
    format for description/comment bodies) into plain text."""
    if not node:
        return ""
    node_type = node.get("type")
    if node_type == "text":
        return node.get("text", "")
    if node_type == "hardBreak":
        return "\n"

    child_text = "".join(adf_to_text(child) for child in node.get("content", []))
    if node_type == "listItem":
        return f"- {child_text.strip()}\n"
    if node_type in ("paragraph", "heading"):
        return f"{child_text}\n\n"
    return child_text


def extract_acceptance_criteria(description_text: str) -> str | None:
    """Best-effort: many teams embed AC as a heading within the description
    body rather than a dedicated custom field (which varies per Jira
    instance and can't be guessed generically — see plan.md §7)."""
    lines = description_text.splitlines()
    for i, line in enumerate(lines):
        if _AC_HEADING_RE.match(line):
            rest = "\n".join(lines[i + 1 :]).strip()
            return rest or None
    return None


class JiraClient:
    def __init__(self):
        self.base_url = config.require(config.JIRA_BASE_URL, "JIRA_BASE_URL").rstrip("/")
        self.auth = HTTPBasicAuth(
            config.require(config.JIRA_EMAIL, "JIRA_EMAIL"),
            config.require(config.JIRA_API_TOKEN, "JIRA_API_TOKEN"),
        )
        self.headers = {"Accept": "application/json"}

    @jira_http_retry
    def ping(self) -> dict:
        """Hello-world call: confirms the base URL + credentials are valid."""
        response = requests.get(
            f"{self.base_url}/rest/api/3/myself",
            headers=self.headers,
            auth=self.auth,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    @jira_http_retry
    def get_issue(self, issue_key: str) -> dict:
        """Fetch a single issue's raw JSON (summary, description, AC, comments)."""
        response = requests.get(
            f"{self.base_url}/rest/api/3/issue/{issue_key}",
            headers=self.headers,
            auth=self.auth,
            params={"fields": "summary,description,comment,status,issuetype"},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def get_issue_content(self, issue_key: str) -> dict:
        """Fetch an issue and flatten it into plain-text fields ready for
        chunking: summary, description, best-effort acceptance criteria, and
        comments."""
        raw = self.get_issue(issue_key)
        fields = raw.get("fields", {})

        description = adf_to_text(fields.get("description")).strip()
        comments = [
            text
            for c in (fields.get("comment") or {}).get("comments", [])
            if (text := adf_to_text(c.get("body")).strip())
        ]

        return {
            "key": raw.get("key", issue_key),
            "summary": fields.get("summary", "") or "",
            "description": description,
            "acceptance_criteria": extract_acceptance_criteria(description),
            "comments": comments,
        }
