"""Tests for the system prompt builder."""

import pytest

from moha_mind.agent.memory import MemoryManager
from moha_mind.agent.system_prompt import build_system_prompt


@pytest.fixture
def memory(tmp_path):
    return MemoryManager(memory_dir=str(tmp_path))


class TestBuildSystemPrompt:
    def test_returns_string(self, memory):
        prompt = build_system_prompt(memory)
        assert isinstance(prompt, str)

    def test_contains_personality(self, memory):
        prompt = build_system_prompt(memory)
        assert "MohaMind" in prompt
        assert "personal AI agent" in prompt

    def test_contains_current_time(self, memory):
        prompt = build_system_prompt(memory)
        assert "Asia/Riyadh" in prompt
        assert "UTC+3" in prompt

    def test_contains_capabilities(self, memory):
        prompt = build_system_prompt(memory)
        assert "save_memory" in prompt
        assert "search_memory" in prompt
        assert "add_task" in prompt

    def test_contains_behavior_rules(self, memory):
        prompt = build_system_prompt(memory)
        assert "BEHAVIOR RULES" in prompt
        assert "SAVE IT" in prompt

    def test_includes_profile(self, memory):
        memory.write("profile", "Name: Moha\nLocation: Riyadh")
        prompt = build_system_prompt(memory)
        assert "PROFILE" in prompt
        assert "Name: Moha" in prompt

    def test_includes_family(self, memory):
        memory.write("family", "Wife: Sarah\nKid: Omar")
        prompt = build_system_prompt(memory)
        assert "FAMILY" in prompt
        assert "Wife: Sarah" in prompt

    def test_includes_tasks(self, memory):
        memory.write("tasks", "# Tasks\n\n## Active\n- [ ] Submit report [HIGH]")
        prompt = build_system_prompt(memory)
        assert "ACTIVE TASKS" in prompt

    def test_omits_empty_categories(self, memory):
        prompt = build_system_prompt(memory)
        assert "### PROFILE" not in prompt

    def test_extra_context(self, memory):
        prompt = build_system_prompt(memory, extra_context="TEST MODE")
        assert "TEST MODE" in prompt
        assert "ADDITIONAL CONTEXT" in prompt

    def test_no_extra_context(self, memory):
        prompt = build_system_prompt(memory)
        assert "ADDITIONAL CONTEXT" not in prompt

    def test_urgent_tasks_section(self, memory):
        memory.write("tasks", "# Tasks\n\n## Active\n- [ ] Urgent task [HIGH] due:2026-04-08")
        prompt = build_system_prompt(memory)
        assert "URGENT TASKS" in prompt
        assert "Urgent task" in prompt

    def test_no_urgent_tasks_no_section(self, memory):
        memory.write("tasks", "# Tasks\n\n## Active\n- [ ] Low task [LOW]")
        prompt = build_system_prompt(memory)
        assert "URGENT TASKS" not in prompt

    def test_expiring_items_section(self, memory):
        from datetime import timedelta

        from moha_mind.utils.timezone import now_ksa

        soon = (now_ksa() + timedelta(days=5)).strftime("%Y-%m-%d")
        memory.write("documents", f"Passport: ABC - Expires: {soon}")
        prompt = build_system_prompt(memory)
        assert "EXPIRING SOON" in prompt

    def test_all_memory_categories_included(self, memory):
        for cat in [
            "profile",
            "family",
            "tasks",
            "occasions",
            "vehicle",
            "finances",
            "health",
            "documents",
            "relationships",
        ]:
            memory.write(cat, f"# {cat}\nTest data")
        prompt = build_system_prompt(memory)
        assert "PROFILE" in prompt
        assert "FAMILY" in prompt
        assert "VEHICLE" in prompt
        assert "FINANCES" in prompt
        assert "HEALTH" in prompt
        assert "DOCUMENTS" in prompt
        assert "RELATIONSHIPS" in prompt
