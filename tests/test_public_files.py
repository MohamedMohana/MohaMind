import pytest

from scripts.check_public_files import check_file


@pytest.mark.parametrize(
    "name",
    [
        ".env",
        ".env.production",
        "credentials/google.json",
        "logs/debug.txt",
        "mcp_servers.json",
        "memory/profile.md",
        "memory/.backups/archive.zip",
        "sessions.db",
        "voice.ogg",
        "ms_token.json",
    ],
)
def test_private_paths_are_rejected(name):
    assert check_file(name, b"innocent content")


@pytest.mark.parametrize("name", [".env.example", "memory/templates/profile.md", "README.md", "memory/.gitkeep"])
def test_public_scaffolding_is_allowed(name):
    assert not check_file(name, b"# Empty template")


@pytest.mark.parametrize(
    "secret",
    [
        b"123456789:" + b"a" * 35,
        b"sk-proj-" + b"a" * 48,
        b"ghp_" + b"a" * 36,
        b"-----BEGIN " + b"PRIVATE KEY-----",
    ],
)
def test_secrets_are_detected_without_returning_the_secret(secret):
    findings = check_file("accidental.txt", secret)
    assert findings
    assert secret.decode() not in str(findings)
