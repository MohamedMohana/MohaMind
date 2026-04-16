"""Tests for MohaMind configuration."""

from moha_mind.config import LLM_PROVIDERS, Settings


class TestSettings:
    def test_default_values(self):
        s = Settings()
        assert s.primary_llm == "zai"
        assert s.fallback_llm == "openai"
        assert s.timezone == "Asia/Riyadh"
        assert s.morning_briefing_time == "08:00"
        assert s.memory_dir == "./memory"
        assert s.log_level == "INFO"
        assert s.zai_model == "glm-5-turbo"
        assert s.openai_model == "gpt-4o-mini"

    def test_memory_path_property(self):
        s = Settings(memory_dir="/tmp/test_memory")
        assert s.memory_path.as_posix() == "/tmp/test_memory"

    def test_active_llm_config_zai(self):
        s = Settings(zai_api_key="zai-key-123", primary_llm="zai")
        config = s.active_llm_config
        assert config["provider"] == "zai"
        assert config["api_key"] == "zai-key-123"
        assert config["model"] == "glm-5-turbo"
        assert config["base_url"] == "https://api.z.ai/api/paas/v4/"

    def test_active_llm_config_openai(self):
        s = Settings(
            openai_api_key="oai-key-456",
            zai_api_key="",
            primary_llm="openai",
        )
        config = s.active_llm_config
        assert config["provider"] == "openai"
        assert config["api_key"] == "oai-key-456"
        assert config["model"] == "gpt-4o-mini"
        assert config["base_url"] is None

    def test_active_llm_config_zai_no_key_falls_to_openai(self):
        s = Settings(zai_api_key="", openai_api_key="oai-key", primary_llm="zai")
        config = s.active_llm_config
        assert config["provider"] == "openai"

    def test_active_llm_config_no_keys_uses_zai_with_missing(self):
        s = Settings(zai_api_key="", openai_api_key="", primary_llm="zai")
        config = s.active_llm_config
        assert config["provider"] == "zai"
        assert config["api_key"] == "missing-key"

    def test_fallback_llm_config_openai(self):
        s = Settings(openai_api_key="oai-key", fallback_llm="openai")
        config = s.fallback_llm_config
        assert config is not None
        assert config["provider"] == "openai"

    def test_fallback_llm_config_zai(self):
        s = Settings(zai_api_key="zai-key", fallback_llm="zai")
        config = s.fallback_llm_config
        assert config is not None
        assert config["provider"] == "zai"

    def test_fallback_llm_config_none(self):
        s = Settings(fallback_llm="none")
        assert s.fallback_llm_config is None

    def test_fallback_llm_config_no_key(self):
        s = Settings(openai_api_key="", zai_api_key="", fallback_llm="openai")
        assert s.fallback_llm_config is None

    def test_custom_model_names(self):
        s = Settings(
            zai_api_key="k",
            zai_model="glm-4-flash",
            openai_api_key="k",
            openai_model="gpt-4o",
        )
        assert s.zai_model == "glm-4-flash"
        assert s.openai_model == "gpt-4o"
        assert s.active_llm_config["model"] == "glm-4-flash"

    def test_llm_providers_dict(self):
        assert "zai" in LLM_PROVIDERS
        assert "openai" in LLM_PROVIDERS
        assert LLM_PROVIDERS["zai"]["base_url"] == "https://api.z.ai/api/paas/v4/"
        assert LLM_PROVIDERS["openai"]["base_url"] is None
