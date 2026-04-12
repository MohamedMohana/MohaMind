"""Tests for setup wizard and doctor."""

from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from moha_mind.cli.setup_wizard import SETUP_STEPS, SetupWizard, run_doctor


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
        with patch("moha_mind.cli.setup_wizard.Path") as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = True
            mock_path_cls.return_value.read_text.return_value = (
                "PRIMARY_LLM=zai\nZAI_API_KEY=sk-test-1234567890abcdef\n"
            )
            mock_path_cls.return_value.resolve.return_value = str(env_file)
            result = run_doctor()
        assert result is True

    def test_doctor_missing_key(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("PRIMARY_LLM=zai\n")
        with patch("moha_mind.cli.setup_wizard.Path") as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = True
            mock_path_cls.return_value.read_text.return_value = "PRIMARY_LLM=zai\n"
            mock_path_cls.return_value.resolve.return_value = str(env_file)
            result = run_doctor()
            result = run_doctor()
        assert result is False
