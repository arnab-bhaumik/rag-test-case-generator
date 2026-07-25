"""GET /config — read-only visibility into non-secret app configuration.
PATCH /config/llm, PATCH /config/jira — update and persist to .env, in
effect immediately (no restart). POST /config/llm/test, POST /config/jira/test
— validate candidate credentials live before saving them.

Secrets are never echoed back by GET or PATCH — only whether they're set."""

from __future__ import annotations

from typing import Literal

import requests
from fastapi import APIRouter
from pydantic import BaseModel
from requests.auth import HTTPBasicAuth

from src import config
from src.generation.llm_client import test_connection as llm_test_connection

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
async def get_config():
    return {
        "llm_provider": config.LLM_PROVIDER,
        "groq_model": config.GROQ_MODEL,
        "groq_configured": bool(config.GROQ_API_KEY),
        "anthropic_model": config.ANTHROPIC_MODEL,
        "anthropic_configured": bool(config.ANTHROPIC_API_KEY),
        "jira_base_url": config.JIRA_BASE_URL,
        "jira_configured": bool(config.JIRA_EMAIL and config.JIRA_API_TOKEN),
        "jira_project_key": config.JIRA_PROJECT_KEY,
    }


class LLMConfigUpdate(BaseModel):
    llm_provider: Literal["groq", "claude"] | None = None
    groq_api_key: str | None = None
    groq_model: str | None = None
    anthropic_api_key: str | None = None
    anthropic_model: str | None = None


@router.patch("/llm")
async def update_llm_config(body: LLMConfigUpdate):
    config.update(
        LLM_PROVIDER=body.llm_provider,
        GROQ_API_KEY=body.groq_api_key,
        GROQ_MODEL=body.groq_model,
        ANTHROPIC_API_KEY=body.anthropic_api_key,
        ANTHROPIC_MODEL=body.anthropic_model,
    )
    return await get_config()


class JiraConfigUpdate(BaseModel):
    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    jira_project_key: str | None = None


@router.patch("/jira")
async def update_jira_config(body: JiraConfigUpdate):
    config.update(
        JIRA_BASE_URL=body.jira_base_url,
        JIRA_EMAIL=body.jira_email,
        JIRA_API_TOKEN=body.jira_api_token,
        JIRA_PROJECT_KEY=body.jira_project_key,
    )
    return await get_config()


class LLMTestRequest(BaseModel):
    provider: Literal["groq", "claude"]
    api_key: str
    model: str


@router.post("/llm/test")
async def test_llm(body: LLMTestRequest):
    try:
        reply = llm_test_connection(body.provider, body.api_key, body.model)
        return {"success": True, "message": f'Connected — model replied "{reply.strip()[:60]}"'}
    except Exception as e:
        return {"success": False, "message": str(e)}


class JiraTestRequest(BaseModel):
    jira_base_url: str
    jira_email: str
    jira_api_token: str


@router.post("/jira/test")
async def test_jira(body: JiraTestRequest):
    try:
        response = requests.get(
            f"{body.jira_base_url.rstrip('/')}/rest/api/3/myself",
            headers={"Accept": "application/json"},
            auth=HTTPBasicAuth(body.jira_email, body.jira_api_token),
            timeout=15,
        )
        response.raise_for_status()
        me = response.json()
        return {"success": True, "message": f"Connected as {me.get('displayName', me.get('accountId'))}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
