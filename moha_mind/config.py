"""MohaMind configuration - all settings from environment variables."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLM_PROVIDERS = {
    "zai": {
        "base_url": "https://api.z.ai/api/paas/v4/",
        "default_model": "glm-5-turbo",
    },
    "openai": {
        "base_url": None,
        "default_model": "gpt-4o-mini",
    },
}

LLMProvider = Literal["zai", "openai"]
LLMStrategy = Literal["solo", "fallback", "verify"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    zai_api_key: str = ""
    zai_model: str = "glm-5-turbo"
    zai_base_url: str = "https://api.z.ai/api/paas/v4/"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""

    primary_llm: LLMProvider = "zai"

    # How the secondary LLM is used:
    #   solo     -> no secondary at all
    #   fallback -> secondary is only called if primary fails
    #   verify   -> secondary reviews primary answers for accuracy
    llm_strategy: LLMStrategy = "fallback"

    # Kept for backwards compatibility with older .env files.
    # If set, it acts as a shortcut to derive strategy + secondary provider.
    fallback_llm: Literal["zai", "openai", "none", ""] = ""

    # Which provider is used as the secondary brain (fallback or verifier)
    secondary_llm: Literal["zai", "openai", "none"] = "openai"

    # Verifier behavior (only used when llm_strategy == "verify")
    verifier_strictness: Literal["lenient", "balanced", "strict"] = "balanced"
    verifier_max_retries: int = 1

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # Extra Telegram user/chat IDs (comma-separated) allowed to talk to the bot
    # in addition to TELEGRAM_CHAT_ID. Everyone else is refused.
    telegram_allowed_user_ids: str = ""
    telegram_allow_destructive: bool = True

    voice_enabled: bool = False
    voice_model: str = "small"
    voice_device: Literal["cpu", "cuda", "auto"] = "cpu"
    voice_compute_type: Literal["int8", "float16", "float32", "int8_float16", "auto"] = "int8"
    voice_language: Literal["auto", "ar", "en"] = "auto"
    voice_cpu_threads: int = Field(default=4, ge=1, le=32)
    voice_max_duration_seconds: int = Field(default=300, ge=1, le=1200)
    voice_max_file_mb: int = Field(default=10, ge=1, le=20)
    voice_local_files_only: bool = False

    @field_validator("voice_model")
    @classmethod
    def validate_voice_model(cls, value: str) -> str:
        value = value.strip()
        if not value or value.endswith(".en") or "distil" in value.lower():
            raise ValueError("Use a multilingual Whisper model such as small, medium, or large-v3")
        return value

    google_credentials_path: str = "./credentials/google_credentials.json"
    google_token_path: str = "./credentials/google_token.json"

    ms_client_id: str = ""
    ms_client_secret: str = ""
    ms_tenant_id: str = "common"
    ms_token_path: str = "./credentials/ms_token.json"

    timezone: str = "Asia/Riyadh"
    # Language for proactive messages (briefings, reminders, alerts) and the
    # instruction sent with Telegram commands: "ar" or "en". Free-form chat
    # always mirrors whatever language the user writes in.
    agent_language: str = "ar"
    morning_briefing_time: str = "08:00"
    weekly_review_day: str = "sun"
    weekly_review_time: str = "19:00"

    memory_dir: str = "./memory"

    # Claude-compatible external MCP servers config ({"mcpServers": {...}}).
    # See mcp_servers.example.json. Missing file = no external servers.
    mcp_servers_config: str = "./mcp_servers.json"

    log_level: str = "INFO"
    # Rotating log files live here (gitignored), next to memory/.
    log_dir: str = "./logs"

    # ----- Memory router + summaries (Phase A) -----
    # When enabled, the system prompt stops pasting every category in full
    # and instead injects rolling summaries plus the top-K relevant categories.
    memory_router_enabled: bool = True
    memory_router_max_categories: int = 4
    memory_summaries_enabled: bool = True
    memory_summary_model: str = ""  # empty = use primary LLM model

    # ----- Semantic memory (Phase B) -----
    # Embedding backend: 'none' | 'openai' | 'local'
    #   none   -> semantic search disabled (FTS5 only)
    #   openai -> uses openai_api_key with text-embedding-3-small by default
    #   local  -> uses sentence-transformers locally (requires optional dep)
    embedding_backend: Literal["none", "openai", "local"] = "none"
    embedding_model: str = ""  # auto-pick based on backend when empty
    semantic_top_k: int = 5

    # ----- Nightly consolidator (Phase C) -----
    consolidator_enabled: bool = False
    # 'auto' applies all changes silently, 'confirm' queues all for approval,
    # 'hybrid' auto-applies low-risk additions and asks for conflicts/sensitive writes.
    consolidator_mode: Literal["auto", "confirm", "hybrid"] = "hybrid"
    consolidator_time: str = "02:30"
    consolidator_send_digest: bool = True

    # ----- Reliability guardian -----
    reliability_guardian_enabled: bool = True
    reliability_guardian_time: str = "03:10"
    reliability_send_digest: bool = True
    memory_backup_retention_days: int = 30
    memory_backup_max_count: int = 60

    # ----- Privacy tiers (cross-cutting) -----
    # Comma-separated category names. Sensitive categories:
    #   - are redacted before being sent to the verifier
    #   - are redacted before being stored in sessions.db (when enabled)
    #   - never appear verbatim in daily_log (when enabled)
    sensitive_categories: str = "finances,health,documents"
    privacy_redact_sessions: bool = True
    privacy_redact_verifier: bool = True
    privacy_redact_daily_log: bool = True

    @property
    def memory_path(self) -> Path:
        return Path(self.memory_dir)

    @property
    def telegram_allowed_ids(self) -> frozenset[str]:
        """All Telegram IDs allowed to talk to the bot (owner chat + extras)."""
        ids = {self.telegram_chat_id.strip()}
        ids.update(part.strip() for part in self.telegram_allowed_user_ids.split(","))
        return frozenset(value for value in ids if value)

    def _provider_config(self, provider: str) -> dict | None:
        if provider == "zai" and self.zai_api_key:
            return {
                "api_key": self.zai_api_key,
                "model": self.zai_model,
                "base_url": self.zai_base_url,
                "provider": "zai",
            }
        if provider == "openai" and self.openai_api_key:
            return {
                "api_key": self.openai_api_key,
                "model": self.openai_model,
                "base_url": self.openai_base_url or None,
                "provider": "openai",
            }
        return None

    @property
    def active_llm_config(self) -> dict:
        cfg = self._provider_config(self.primary_llm)
        if cfg:
            return cfg
        other = "openai" if self.primary_llm == "zai" else "zai"
        fallback_cfg = self._provider_config(other)
        if fallback_cfg:
            return fallback_cfg
        # No keys at all — return a dummy config that will fail politely.
        if self.primary_llm == "zai":
            return {
                "api_key": self.zai_api_key or "missing-key",
                "model": self.zai_model,
                "base_url": self.zai_base_url,
                "provider": "zai",
            }
        return {
            "api_key": self.openai_api_key or "missing-key",
            "model": self.openai_model,
            "base_url": self.openai_base_url or None,
            "provider": "openai",
        }

    @property
    def _resolved_secondary_provider(self) -> str:
        """Decide which provider is the secondary brain.

        Precedence:
          1. Legacy `fallback_llm` env value (when set to a real provider) —
             this keeps backwards compatibility with existing .env files.
          2. Explicit `secondary_llm` env value (when not 'none').
          3. The opposite of the primary provider.
        """
        if self.fallback_llm and self.fallback_llm not in ("none", ""):
            return self.fallback_llm
        if self.secondary_llm and self.secondary_llm != "none":
            return self.secondary_llm
        return "openai" if self.primary_llm == "zai" else "zai"

    @property
    def _strategy_effective(self) -> LLMStrategy:
        """Normalize legacy config to a strategy value."""
        # Legacy: fallback_llm="none" used to mean "no secondary".
        if self.secondary_llm == "none" or self.fallback_llm == "none":
            return "solo"
        return self.llm_strategy

    @property
    def fallback_llm_config(self) -> dict | None:
        """Return the secondary LLM config when it should act as a FALLBACK.

        Returns None when the strategy is not "fallback" or no secondary key exists.
        """
        if self._strategy_effective != "fallback":
            return None
        return self._provider_config(self._resolved_secondary_provider)

    @property
    def verifier_llm_config(self) -> dict | None:
        """Return the secondary LLM config when it should act as a VERIFIER."""
        if self._strategy_effective != "verify":
            return None
        return self._provider_config(self._resolved_secondary_provider)

    @property
    def secondary_llm_config(self) -> dict | None:
        """Return the secondary LLM config (either fallback or verifier role)."""
        if self._strategy_effective == "solo":
            return None
        return self._provider_config(self._resolved_secondary_provider)

    @property
    def effective_strategy(self) -> LLMStrategy:
        """Public accessor for the resolved strategy."""
        return self._strategy_effective


settings = Settings()
