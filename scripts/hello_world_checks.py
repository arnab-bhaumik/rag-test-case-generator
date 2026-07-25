"""Sprint 0 checks: verify each configured provider (Groq/Claude, Jira) actually
works before building on top of them. Run with: python -m scripts.hello_world_checks
Requires the relevant keys to be set in .env (copy from .env.example).
"""

from src import config
from src.generation.llm_client import LLMClient
from src.ingestion.jira_client import JiraClient


def check_llm(provider: str) -> None:
    try:
        client = LLMClient(provider=provider)
        reply = client.complete("Reply with exactly: OK")
        print(f"[{provider}] OK -> {reply.strip()!r}")
    except Exception as e:
        print(f"[{provider}] SKIPPED/FAILED -> {e}")


def check_jira() -> None:
    try:
        me = JiraClient().ping()
        print(f"[jira] OK -> authenticated as {me.get('displayName', me.get('accountId'))}")
    except Exception as e:
        print(f"[jira] SKIPPED/FAILED -> {e}")


if __name__ == "__main__":
    if config.GROQ_API_KEY:
        check_llm("groq")
    else:
        print("[groq] SKIPPED -> GROQ_API_KEY not set")

    if config.ANTHROPIC_API_KEY:
        check_llm("claude")
    else:
        print("[claude] SKIPPED -> ANTHROPIC_API_KEY not set")

    if config.JIRA_BASE_URL and config.JIRA_EMAIL and config.JIRA_API_TOKEN:
        check_jira()
    else:
        print("[jira] SKIPPED -> JIRA_BASE_URL/JIRA_EMAIL/JIRA_API_TOKEN not set")
