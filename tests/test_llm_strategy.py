"""Tests for the LLM strategy system (solo / fallback / verify)."""

from moha_mind.config import Settings


class TestLLMStrategyConfig:
    def test_solo_strategy_disables_secondary(self):
        s = Settings(
            primary_llm="zai",
            zai_api_key="zai-key",
            openai_api_key="oai-key",
            llm_strategy="solo",
        )
        assert s.effective_strategy == "solo"
        assert s.secondary_llm_config is None
        assert s.fallback_llm_config is None
        assert s.verifier_llm_config is None

    def test_fallback_strategy_returns_fallback_only(self):
        s = Settings(
            primary_llm="zai",
            zai_api_key="zai-key",
            openai_api_key="oai-key",
            llm_strategy="fallback",
        )
        assert s.effective_strategy == "fallback"
        assert s.fallback_llm_config is not None
        assert s.fallback_llm_config["provider"] == "openai"
        assert s.verifier_llm_config is None

    def test_verify_strategy_returns_verifier_only(self):
        s = Settings(
            primary_llm="zai",
            zai_api_key="zai-key",
            openai_api_key="oai-key",
            llm_strategy="verify",
        )
        assert s.effective_strategy == "verify"
        assert s.verifier_llm_config is not None
        assert s.verifier_llm_config["provider"] == "openai"
        assert s.fallback_llm_config is None

    def test_legacy_fallback_none_forces_solo(self):
        s = Settings(
            primary_llm="zai",
            zai_api_key="zai-key",
            openai_api_key="oai-key",
            fallback_llm="none",
            llm_strategy="fallback",
        )
        assert s.effective_strategy == "solo"
        assert s.fallback_llm_config is None

    def test_secondary_provider_prefers_legacy_fallback_llm(self):
        s = Settings(
            primary_llm="zai",
            zai_api_key="zai-key",
            openai_api_key="oai-key",
            fallback_llm="zai",
        )
        # legacy fallback_llm=zai means secondary=zai (even though primary is zai)
        assert s._resolved_secondary_provider == "zai"

    def test_verifier_needs_secondary_key(self):
        s = Settings(
            primary_llm="zai",
            zai_api_key="zai-key",
            openai_api_key="",
            llm_strategy="verify",
        )
        # Strategy is verify but openai has no key — secondary config must be None.
        assert s.verifier_llm_config is None

    def test_effective_strategy_default_is_fallback(self):
        s = Settings(zai_api_key="zai-key")
        assert s.effective_strategy == "fallback"

    def test_openai_base_url_override(self):
        s = Settings(
            primary_llm="openai",
            openai_api_key="oai-key",
            openai_base_url="https://proxy.example/v1",
        )
        assert s.active_llm_config["base_url"] == "https://proxy.example/v1"
