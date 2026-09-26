"""Tests for MohaMind configuration.

Settings are built with `_env_file=None` and scrubbed environment variables
so the assertions hold for every contributor and on CI — regardless of any
local .env or exported keys.
"""

import pytest
from pydantic import ValidationError

from moha_mind.config import LLM_PROVIDERS, Settings

ENV_KEYS = [name.upper() for name in Settings.model_fields]


@pytest.fixture
def make_settings(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    def _make(**kwargs):
        return Settings(_env_file=None, **kwargs)

    return _make


class TestSettings:
    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("agent_max_tool_rounds", 0),
            ("agent_max_tool_rounds", 101),
            ("agent_max_tool_calls", 0),
            ("agent_max_tool_calls", 501),
            ("agent_tool_timeout_seconds", 0),
            ("agent_tool_timeout_seconds", float("nan")),
            ("agent_tool_timeout_seconds", float("inf")),
            ("agent_max_tool_result_chars", 127),
            ("agent_max_tool_result_chars", 1000001),
        ],
    )
    def test_invalid_execution_limits(self, make_settings, name, value):
        with pytest.raises(ValidationError):
            make_settings(**{name: value})

    def test_default_values(self, make_settings):
        s = make_settings()
        assert s.primary_llm == "zai"
        assert s.llm_strategy == "fallback"
        assert s.fallback_llm == ""  # legacy shortcut is unset by default
        assert s.secondary_llm == "openai"
        assert s.timezone == "Asia/Riyadh"
        assert s.agent_language == "ar"
        assert s.morning_briefing_time == "08:00"
        assert s.memory_dir == "./memory"
        assert s.log_level == "INFO"
        assert s.zai_model == "glm-5-turbo"
        assert s.openai_model == "gpt-4o-mini"

    def test_memory_path_property(self, make_settings):
        s = make_settings(memory_dir="/tmp/test_memory")
        assert s.memory_path.as_posix() == "/tmp/test_memory"

    def test_active_llm_config_zai(self, make_settings):
        s = make_settings(zai_api_key="zai-key-123", primary_llm="zai")
        config = s.active_llm_config
        assert config["provider"] == "zai"
        assert config["api_key"] == "zai-key-123"
        assert config["model"] == "glm-5-turbo"
        assert config["base_url"] == "https://api.z.ai/api/paas/v4/"

    def test_active_llm_config_openai(self, make_settings):
        s = make_settings(
            openai_api_key="oai-key-456",
            zai_api_key="",
            primary_llm="openai",
        )
        config = s.active_llm_config
        assert config["provider"] == "openai"
        assert config["api_key"] == "oai-key-456"
        assert config["model"] == "gpt-4o-mini"
        assert config["base_url"] is None

    def test_active_llm_config_zai_no_key_falls_to_openai(self, make_settings):
        s = make_settings(zai_api_key="", openai_api_key="oai-key", primary_llm="zai")
        config = s.active_llm_config
        assert config["provider"] == "openai"

    def test_active_llm_config_no_keys_uses_zai_with_missing(self, make_settings):
        s = make_settings(zai_api_key="", openai_api_key="", primary_llm="zai")
        config = s.active_llm_config
        assert config["provider"] == "zai"
        assert config["api_key"] == "missing-key"

    def test_fallback_llm_config_openai(self, make_settings):
        s = make_settings(openai_api_key="oai-key", fallback_llm="openai")
        config = s.fallback_llm_config
        assert config is not None
        assert config["provider"] == "openai"

    def test_fallback_llm_config_zai(self, make_settings):
        s = make_settings(zai_api_key="zai-key", fallback_llm="zai")
        config = s.fallback_llm_config
        assert config is not None
        assert config["provider"] == "zai"

    def test_fallback_llm_config_none(self, make_settings):
        s = make_settings(fallback_llm="none")
        assert s.fallback_llm_config is None

    def test_fallback_llm_config_no_key(self, make_settings):
        s = make_settings(openai_api_key="", zai_api_key="", fallback_llm="openai")
        assert s.fallback_llm_config is None

    def test_custom_model_names(self, make_settings):
        s = make_settings(
            zai_api_key="k",
            zai_model="glm-4-flash",
            openai_api_key="k",
            openai_model="gpt-4o",
        )
        assert s.zai_model == "glm-4-flash"
        assert s.openai_model == "gpt-4o"
        assert s.active_llm_config["model"] == "glm-4-flash"

    def test_telegram_allowed_ids_default_empty(self, make_settings):
        s = make_settings()
        assert s.telegram_allowed_ids == frozenset()

    def test_llm_providers_dict(self):
        assert "zai" in LLM_PROVIDERS
        assert "openai" in LLM_PROVIDERS
        assert LLM_PROVIDERS["zai"]["base_url"] == "https://api.z.ai/api/paas/v4/"
        assert LLM_PROVIDERS["openai"]["base_url"] is None
