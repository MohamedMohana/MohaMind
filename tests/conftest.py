"""Shared test fixtures for MohaMind tests."""

import pytest

from moha_mind.agent.memory import MemoryManager


@pytest.fixture
def tmp_memory(tmp_path):
    memory = MemoryManager(memory_dir=str(tmp_path))
    memory.ensure_templates()
    return memory
