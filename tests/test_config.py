import pytest
from dotenv import dotenv_values

from src import config


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Points config.update() at a throwaway .env instead of the real one,
    and restores the module's real globals afterward so other tests (and
    the live app) aren't left with test values."""
    fake_env = tmp_path / ".env"
    fake_env.write_text("")
    monkeypatch.setattr(config, "ENV_PATH", fake_env)

    saved = {k: getattr(config, k) for k in ("GROQ_API_KEY", "GROQ_MODEL", "JIRA_BASE_URL", "LLM_PROVIDER")}
    yield fake_env
    for k, v in saved.items():
        setattr(config, k, v)


def test_update_sets_in_memory_value_immediately(isolated_env):
    config.update(GROQ_API_KEY="gsk_test123")
    assert config.GROQ_API_KEY == "gsk_test123"


def test_update_persists_to_env_file(isolated_env):
    config.update(GROQ_API_KEY="gsk_test123")
    values = dotenv_values(str(isolated_env))
    assert values["GROQ_API_KEY"] == "gsk_test123"


def test_update_skips_blank_values():
    original = config.GROQ_API_KEY
    config.update(GROQ_API_KEY="")
    assert config.GROQ_API_KEY == original


def test_update_skips_none_values():
    original = config.JIRA_BASE_URL
    config.update(JIRA_BASE_URL=None)
    assert config.JIRA_BASE_URL == original


def test_update_lowercases_llm_provider(isolated_env):
    config.update(LLM_PROVIDER="Claude")
    assert config.LLM_PROVIDER == "claude"


def test_update_rejects_unknown_key(isolated_env):
    with pytest.raises(ValueError):
        config.update(NOT_A_REAL_CONFIG_KEY="x")


def test_update_only_touches_given_keys(isolated_env):
    before = config.JIRA_EMAIL
    config.update(GROQ_API_KEY="gsk_test123")
    assert config.JIRA_EMAIL == before
