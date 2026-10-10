from unittest.mock import AsyncMock, Mock, patch

import pytest

from moha_mind import main
from moha_mind.config import Settings


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


@pytest.mark.parametrize("key", ["", "your-zai-api-key", "missing-key"])
def test_placeholder_key_does_not_skip_onboarding(tmp_path, key):
    (tmp_path / ".env").write_text(f"ZAI_API_KEY={key}\n")
    assert main._has_api_key() is False
    assert Settings().zai_api_key == ""


def test_quoted_exported_key_is_detected(tmp_path):
    (tmp_path / ".env").write_text("export OPENAI_API_KEY='fictional-key' # example\n")
    assert main._has_api_key() is True


def test_empty_shell_key_overrides_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=file-key\n")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert main._has_api_key() is False


def test_first_run_refreshes_existing_settings_and_preserves_file(tmp_path, monkeypatch):
    from moha_mind import config

    (tmp_path / ".env").write_text("# preserve\nMEMORY_DIR=./existing-memory\nCUSTOM_VAR=keep\n")
    original = Settings()
    monkeypatch.setattr(config, "settings", original)
    with patch(
        "moha_mind.cli.setup_wizard.Prompt.ask",
        side_effect=[
            "openai",
            "fictional-key",
            "Asia/Riyadh",
            "en",
        ],
    ):
        main._first_run_auth()

    assert config.settings is original
    assert original.active_llm_config["api_key"] == "fictional-key"
    assert original.active_llm_config["provider"] == "openai"
    assert original.agent_language == "en"
    assert original.memory_dir == "./existing-memory"
    assert "CUSTOM_VAR=keep" in (tmp_path / ".env").read_text()


@pytest.mark.parametrize("args", [[], ["--bot"], ["-p", "hello"]])
def test_missing_key_noninteractive_exits_with_next_steps(monkeypatch, capsys, args):
    monkeypatch.setattr("sys.argv", ["mohamind", *args])
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    onboarding = Mock()
    monkeypatch.setattr(main, "_first_run_auth", onboarding)
    with pytest.raises(SystemExit) as exc:
        main.run()
    assert exc.value.code == 1
    onboarding.assert_not_called()
    output = capsys.readouterr().err
    assert "setup --quick" in output
    assert "mohamind demo" in output


def test_interactive_first_run_starts_cli_after_setup(monkeypatch):
    monkeypatch.setattr("sys.argv", ["mohamind"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    onboarding = Mock()
    run = AsyncMock()
    monkeypatch.setattr(main, "_first_run_auth", onboarding)
    monkeypatch.setattr(main, "configure_logging", Mock())
    monkeypatch.setattr(main, "run_cli", run)
    main.run()
    onboarding.assert_called_once()
    run.assert_awaited_once_with(with_bot=False, initial_prompt=None)


@pytest.mark.parametrize("healthy", [True, False])
def test_doctor_exit_status(monkeypatch, healthy):
    monkeypatch.setattr("sys.argv", ["mohamind", "doctor"])
    monkeypatch.setattr("moha_mind.cli.setup_wizard.run_doctor", lambda: healthy)
    if healthy:
        main.run()
    else:
        with pytest.raises(SystemExit) as exc:
            main.run()
        assert exc.value.code == 1
