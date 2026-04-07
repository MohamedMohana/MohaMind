"""MohaMind configuration - all settings from environment variables."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LLM_PROVIDERS = {
    "zai": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "default_model": "glm-4-plus",
    },
    "openai": {
        "base_url": None,
        "default_model": "gpt-4o-mini",
    },
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    zai_api_key: str = ""
    zai_model: str = "glm-4-plus"
    zai_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    primary_llm: Literal["zai", "openai"] = "zai"

    fallback_llm: Literal["zai", "openai", "none"] = "openai"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    google_credentials_path: str = "./credentials/google_credentials.json"
    google_token_path: str = "./credentials/google_token.json"

    ms_client_id: str = ""
    ms_client_secret: str = ""
    ms_tenant_id: str = "common"
    ms_token_path: str = "./credentials/ms_token.json"

    timezone: str = "Asia/Riyadh"
    morning_briefing_time: str = "08:00"
    weekly_review_day: str = "sun"
    weekly_review_time: str = "19:00"

    memory_dir: str = "./memory"

    log_level: str = "INFO"

    @property
    def memory_path(self) -> Path:
        return Path(self.memory_dir)

    @property
    def active_llm_config(self) -> dict:
        if self.primary_llm == "zai" and self.zai_api_key:
            return {
                "api_key": self.zai_api_key,
                "model": self.zai_model,
                "base_url": self.zai_base_url,
                "provider": "zai",
            }
        if self.openai_api_key:
            return {
                "api_key": self.openai_api_key,
                "model": self.openai_model,
                "base_url": None,
                "provider": "openai",
            }
        return {
            "api_key": self.zai_api_key or "missing-key",
            "model": self.zai_model,
            "base_url": self.zai_base_url,
            "provider": "zai",
        }

    @property
    def fallback_llm_config(self) -> dict | None:
        if self.fallback_llm == "none":
            return None
        if self.fallback_llm == "openai" and self.openai_api_key:
            return {
                "api_key": self.openai_api_key,
                "model": self.openai_model,
                "base_url": None,
                "provider": "openai",
            }
        if self.fallback_llm == "zai" and self.zai_api_key:
            return {
                "api_key": self.zai_api_key,
                "model": self.zai_model,
                "base_url": self.zai_base_url,
                "provider": "zai",
            }
        return None


settings = Settings()
