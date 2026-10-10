import shutil
import subprocess
from pathlib import Path

import pytest

BRIDGE = Path(__file__).resolve().parents[1] / "moha_mind" / "whatsapp_bot" / "bridge"


@pytest.mark.parametrize(("option", "filename"), [("--test", "policy.test.mjs"), ("--check", "bridge.mjs")])
def test_node_bridge_checks(option, filename):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Optional WhatsApp bridge requires Node.js")
    version = subprocess.run([node, "--version"], capture_output=True, text=True, check=True, timeout=10)
    if int(version.stdout.strip().lstrip("v").split(".")[0]) < 20:
        pytest.skip("Optional WhatsApp bridge requires Node.js 20 or newer")
    result = subprocess.run([node, option, str(BRIDGE / filename)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
