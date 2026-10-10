"""Tests for setup wizard and doctor."""

from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import dotenv_values
from rich.console import Console

from moha_mind.cli.setup_wizard import SETUP_STEPS, SetupWizard, run_doctor
from moha_mind.config import Settings


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


class TestSetupWizard:
    def test_mask_short(self):
        wizard = SetupWizard()
        assert wizard._mask("") == "(not set)"
        assert wizard._mask("ab") == "**"

    def test_mask_long(self):
        wizard = SetupWizard()
        result = wizard._mask("sk-1234567890abcdef")
        assert result.startswith("sk-1")
        assert result.endswith("cdef")
        assert "*" in result

    def test_mask_8_chars(self):
        wizard = SetupWizard()
        result = wizard._mask("12345678")
        assert "*" in result

    def test_is_step_needed_no_condition(self):
        wizard = SetupWizard()
        step = {"key": "TEST", "label": "Test"}
        assert wizard._is_step_needed(step, {}) is True

    def test_is_step_needed_condition_met(self):
        wizard = SetupWizard()
        step = {"key": "ZAI_KEY", "required_if": {"PRIMARY_LLM": "zai"}}
        assert wizard._is_step_needed(step, {"PRIMARY_LLM": "zai"}) is True

    def test_is_step_needed_condition_not_met(self):
        wizard = SetupWizard()
        step = {"key": "ZAI_KEY", "required_if": {"PRIMARY_LLM": "zai"}}
        assert wizard._is_step_needed(step, {"PRIMARY_LLM": "openai"}) is False

    def test_load_existing_no_file(self, tmp_path):
        wizard = SetupWizard()
        with patch.object(Path, "exists", return_value=False):
            result = wizard._load_existing()
        assert isinstance(result, dict)

    def test_load_existing_with_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("PRIMARY_LLM=openai\nZAI_API_KEY=test123\n")
        wizard = SetupWizard()
        with patch("moha_mind.cli.setup_wizard.ENV_PATH", env_file):
            result = wizard._load_existing()
        assert result.get("PRIMARY_LLM") == "openai"
        assert result.get("ZAI_API_KEY") == "test123"

    def test_load_existing_skips_comments(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\nPRIMARY_LLM=zai\n\n# another\n")
        wizard = SetupWizard()
        with patch("moha_mind.cli.setup_wizard.ENV_PATH", env_file):
            result = wizard._load_existing()
        assert result.get("PRIMARY_LLM") == "zai"
        assert "# comment" not in result

    def test_show_welcome(self):
        console = Console(force_terminal=True, width=100)
        wizard = SetupWizard(console)
        wizard.show_welcome()

    def test_show_current_config_empty(self):
        console = Console(force_terminal=True, width=100)
        wizard = SetupWizard(console)
        wizard.show_current_config({})

    def test_show_current_config_with_values(self):
        console = Console(force_terminal=True, width=100)
        wizard = SetupWizard(console)
        wizard.show_current_config({"PRIMARY_LLM": "zai", "ZAI_API_KEY": "sk-test-12345678"})

    def test_save_config(self, tmp_path):
        env_file = tmp_path / ".env"
        wizard = SetupWizard()
        with patch("moha_mind.cli.setup_wizard.ENV_PATH", env_file):
            wizard.save_config({"PRIMARY_LLM": "zai", "ZAI_API_KEY": "test-key-123"})
        content = env_file.read_text()
        assert "PRIMARY_LLM=zai" in content
        assert "ZAI_API_KEY=test-key-123" in content

    def test_save_config_preserves_existing(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# My comment\nCUSTOM_VAR=hello\n")
        wizard = SetupWizard()
        with patch("moha_mind.cli.setup_wizard.ENV_PATH", env_file):
            wizard.save_config({"PRIMARY_LLM": "openai"})
        content = env_file.read_text()
        assert "CUSTOM_VAR=hello" in content
        assert "PRIMARY_LLM=openai" in content
        assert "# My comment" in content

    def test_save_config_round_trips_special_values(self, tmp_path):
        config = {"OPENAI_API_KEY": "fictional-key # with ' quotes", "MEMORY_DIR": "./my memory", "CUSTOM_VAR": ""}
        SetupWizard().save_config(config)
        assert dotenv_values(tmp_path / ".env") == config

    def test_load_existing_matches_dotenv_and_shell_precedence(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("export PRIMARY_LLM='openai'\nOPENAI_API_KEY='file-key' # note\n")
        monkeypatch.setenv("OPENAI_API_KEY", "shell-key")
        monkeypatch.setenv("SECONDARY_LLM", "none")
        loaded = SetupWizard()._load_existing()
        assert loaded["PRIMARY_LLM"] == "openai"
        assert loaded["OPENAI_API_KEY"] == "shell-key"
        assert loaded["SECONDARY_LLM"] == "none"

    def test_empty_shell_value_overrides_file(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("OPENAI_API_KEY=file-key\n")
        monkeypatch.setenv("OPENAI_API_KEY", "")
        assert SetupWizard()._load_existing()["OPENAI_API_KEY"] == ""

    def test_quick_setup_only_asks_four_questions(self, tmp_path):
        with patch(
            "moha_mind.cli.setup_wizard.Prompt.ask",
            side_effect=[
                "openai",
                "fictional-key",
                "Asia/Riyadh",
                "en",
            ],
        ) as ask:
            result = SetupWizard().run(quick=True)
        assert ask.call_count == 4
        assert ask.call_args_list[1].kwargs["password"] is True
        assert result["LLM_STRATEGY"] == "solo"
        assert result["SECONDARY_LLM"] == "none"
        assert result["OPENAI_API_KEY"] == "fictional-key"
        assert "TELEGRAM_BOT_TOKEN" not in dotenv_values(tmp_path / ".env")

    def test_quick_setup_preserves_existing_configuration(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text(
            "# keep this\nMEMORY_DIR=./custom-memory\nTELEGRAM_CHAT_ID=123\n"
            "CUSTOM_VAR=custom-value\nOPENAI_API_KEY=existing-key\nLLM_STRATEGY=verify\n"
            "FALLBACK_LLM=zai\nSECONDARY_LLM=zai\n"
        )
        with (
            patch("moha_mind.cli.setup_wizard.Prompt.ask", side_effect=["openai", "Asia/Riyadh", "en"]),
            patch("moha_mind.cli.setup_wizard.Confirm.ask", return_value=True),
        ):
            SetupWizard().run(quick=True)
        config = dotenv_values(env)
        assert config["MEMORY_DIR"] == "./custom-memory"
        assert config["TELEGRAM_CHAT_ID"] == "123"
        assert config["CUSTOM_VAR"] == "custom-value"
        assert config["LLM_STRATEGY"] == "verify"
        assert config["FALLBACK_LLM"] == "zai"
        assert "# keep this" in env.read_text()

    def test_quick_setup_cancellation_does_not_write_partial_config(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("CUSTOM_VAR=keep-this\n")
        before = env.read_bytes()
        with patch("moha_mind.cli.setup_wizard.Prompt.ask", side_effect=["openai", KeyboardInterrupt]):
            with pytest.raises(KeyboardInterrupt):
                SetupWizard().run(quick=True)
        assert env.read_bytes() == before

    @pytest.mark.parametrize("invalid", ["", "your-openai-key", "missing-key"])
    def test_key_prompt_rejects_placeholders(self, invalid):
        step = next(step for step in SETUP_STEPS if step["key"] == "OPENAI_API_KEY")
        with patch("moha_mind.cli.setup_wizard.Prompt.ask", side_effect=[invalid, "fictional-key"]) as ask:
            assert SetupWizard().configure_step(step, {}) == "fictional-key"
        assert ask.call_count == 2

    def test_timezone_prompt_retries_invalid_zone(self):
        step = next(step for step in SETUP_STEPS if step["key"] == "TIMEZONE")
        with patch("moha_mind.cli.setup_wizard.Prompt.ask", side_effect=["Mars/Olympus", "Europe/London"]) as ask:
            assert SetupWizard().configure_step(step, {}) == "Europe/London"
        assert ask.call_count == 2


class TestSetupSteps:
    def test_all_steps_have_keys(self):
        for step in SETUP_STEPS:
            assert "key" in step
            assert "label" in step
            assert "category" in step

    def test_primary_llm_has_choices(self):
        llm_step = next(s for s in SETUP_STEPS if s["key"] == "PRIMARY_LLM")
        assert "choices" in llm_step
        assert "zai" in llm_step["choices"]
        assert "openai" in llm_step["choices"]

    def test_secret_keys_masked(self):
        secret_steps = [s for s in SETUP_STEPS if s.get("secret")]
        assert len(secret_steps) >= 2
        for step in secret_steps:
            assert step.get("secret") is True


class TestDoctor:
    def test_doctor_with_no_env(self, tmp_path):
        with patch("moha_mind.cli.setup_wizard.ENV_PATH", tmp_path / "nonexistent"):
            result = run_doctor()
        assert isinstance(result, bool)

    def test_doctor_with_env(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("PRIMARY_LLM=zai\nZAI_API_KEY=sk-test-1234567890abcdef\n")
        result = run_doctor()
        assert result is True

    def test_doctor_missing_key(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("PRIMARY_LLM=zai\n")
        result = run_doctor()
        assert result is False

    def test_doctor_rejects_placeholder_keys(self, tmp_path):
        (tmp_path / ".env").write_text("ZAI_API_KEY=your-zai-api-key\nOPENAI_API_KEY=your-openai-key\n")
        assert run_doctor() is False

    def test_doctor_accepts_shell_only_config(self, monkeypatch, capsys):
        monkeypatch.setenv("OPENAI_API_KEY", "fictional-key")
        assert run_doctor() is True
        output = capsys.readouterr().out
        assert "Local configuration ready" in output
        assert "connectivity are not tested" in output
        assert "fictional-key" not in output

    def test_doctor_uses_shell_over_file(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("ZAI_API_KEY=file-key\n")
        monkeypatch.setenv("ZAI_API_KEY", "")
        assert run_doctor() is False

    def test_doctor_rejects_invalid_timezone(self, tmp_path):
        (tmp_path / ".env").write_text("ZAI_API_KEY=fictional-key\nTIMEZONE=Mars/Olympus\n")
        assert run_doctor() is False

    def test_doctor_explains_reminder_delivery(self, monkeypatch, capsys):
        monkeypatch.setenv("OPENAI_API_KEY", "fictional-key")
        assert run_doctor() is True
        assert "--bot or --all" in capsys.readouterr().out
