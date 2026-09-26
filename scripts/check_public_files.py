from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path, PurePosixPath

SECRET_PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "Telegram bot token": re.compile(rb"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"),
    "provider API key": re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b"),
    "GitHub token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
}


def check_file(name: str, data: bytes) -> list[str]:
    path = PurePosixPath(name)
    problems = []
    if path.name.startswith(".env") and path.name != ".env.example":
        problems.append("local environment file")
    if {"credentials", "logs", "backups", "models"} & set(path.parts):
        problems.append("private runtime directory")
    if path.name == "mcp_servers.json":
        problems.append("local MCP configuration")
    if path.parts[0] == "memory" and name not in {"memory/.gitkeep", "memory/README.md"}:
        if len(path.parts) < 3 or path.parts[1] != "templates":
            problems.append("personal memory file")
    if re.search(r"\.(?:db(?:-.*)?|sqlite\w*|log|token|pem|key|ogg|oga|wav|mp3|m4a|flac|zip)$", name, re.I):
        problems.append("private data or recording file")
    if path.name.endswith("_token.json"):
        problems.append("OAuth token file")
    problems.extend(label for label, pattern in SECRET_PATTERNS.items() if pattern.search(data))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Check public Git files without printing secrets or file contents")
    parser.add_argument("--staged", action="store_true", help="Inspect the exact Git index before committing")
    args = parser.parse_args()
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    failures = 0
    for name in filter(None, names):
        path = root / name
        if args.staged:
            data = subprocess.check_output(["git", "show", f":{name}"], cwd=root)
        elif path.is_symlink():
            print(f"{name}: symbolic link requires review")
            failures += 1
            continue
        elif path.is_file():
            data = path.read_bytes()
        else:
            continue
        for problem in check_file(name, data):
            print(f"{name}: {problem}")
            failures += 1
    print("Public-file check passed." if not failures else f"Public-file check failed: {failures} finding(s).")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
