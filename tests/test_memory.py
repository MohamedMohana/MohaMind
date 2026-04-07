"""Tests for MohaMind memory system."""

import pytest

from moha_mind.agent.memory import MemoryManager


@pytest.fixture
def memory(tmp_path):
    return MemoryManager(memory_dir=str(tmp_path))


class TestMemoryManager:
    def test_write_and_read(self, memory):
        memory.write("profile", "# Test Profile\nName: Moha")
        content = memory.read("profile")
        assert "Moha" in content

    def test_read_nonexistent(self, memory):
        content = memory.read("nonexistent")
        assert content == ""

    def test_append(self, memory):
        memory.write("tasks", "# Tasks\n")
        memory.append("tasks", "- [ ] New task")
        content = memory.read("tasks")
        assert "New task" in content

    def test_append_to_section(self, memory):
        memory.write("tasks", "# Tasks\n\n## Active\n- [ ] Existing task\n")
        memory.append_to_section("tasks", "Active", "- [ ] New task")
        content = memory.read("tasks")
        assert "Existing task" in content
        assert "New task" in content

    def test_append_to_new_section(self, memory):
        memory.write("tasks", "# Tasks\n")
        memory.append_to_section("tasks", "New Section", "- item")
        content = memory.read("tasks")
        assert "New Section" in content
        assert "- item" in content

    def test_search(self, memory):
        memory.write("profile", "# Profile\nName: Moha\nLocation: Riyadh")
        memory.write("tasks", "# Tasks\nCall Moha tomorrow")
        results = memory.search("Moha")
        assert len(results) >= 2

    def test_search_empty(self, memory):
        results = memory.search("nothing")
        assert results == []

    def test_search_specific_categories(self, memory):
        memory.write("profile", "Name: Moha")
        memory.write("tasks", "Task for Moha")
        results = memory.search("Moha", categories=["profile"])
        assert len(results) == 1
        assert results[0]["category"] == "profile"

    def test_get_all_context(self, memory):
        memory.write("profile", "# Profile\nName: Moha")
        memory.write("tasks", "# Tasks\nDo something")
        context = memory.get_all_context()
        assert "PROFILE" in context
        assert "TASKS" in context

    def test_save_daily_log(self, memory):
        memory.save_daily_log("Had a great conversation today")
        from moha_mind.utils.timezone import ksa_today_str

        log_path = memory.memory_path / "daily_log" / f"{ksa_today_str()}.md"
        assert log_path.exists()
        assert "great conversation" in log_path.read_text()

    def test_save_note(self, memory):
        path = memory.save_note("Test Note", "Some content here")
        assert path.exists()
        assert "Some content here" in path.read_text()

    def test_list_notes(self, memory):
        memory.save_note("First Note", "content 1")
        memory.save_note("Second Note", "content 2")
        notes = memory.list_notes()
        assert len(notes) == 2

    def test_add_task(self, memory):
        memory.write("tasks", "# Tasks\n\n## Active\n")
        memory.add_task("Buy groceries", priority="high", due="2026-04-10")
        content = memory.read("tasks")
        assert "Buy groceries" in content
        assert "[HIGH]" in content
        assert "due:2026-04-10" in content

    def test_complete_task(self, memory):
        memory.write("tasks", "# Tasks\n\n## Active\n- [ ] Call mom\n")
        result = memory.complete_task("Call mom")
        assert result is True
        content = memory.read("tasks")
        assert "- [x] Call mom" in content

    def test_complete_task_not_found(self, memory):
        result = memory.complete_task("nonexistent task")
        assert result is False

    def test_get_expiring_items(self, memory):
        from datetime import timedelta

        from moha_mind.utils.timezone import now_ksa

        next_month = (now_ksa() + timedelta(days=15)).strftime("%Y-%m-%d")
        memory.write("documents", f"# Docs\nPassport: ABC123 - Expires: {next_month}\n")
        items = memory.get_expiring_items(days_ahead=30)
        assert len(items) >= 1
        assert any("Passport" in i["detail"] for i in items)

    def test_ensure_templates(self, memory):
        memory.ensure_templates()
        for category in ["profile", "tasks", "vehicle", "finances", "health", "home", "documents"]:
            content = memory.read(category)
            assert content != "", f"Template for {category} should exist"

    def test_get_task_section(self, memory):
        memory.write(
            "tasks",
            "# Tasks\n\n## Active\n- [ ] Task one [HIGH] due:2026-04-15\n- [x] Task two\n- [ ] Task three [LOW]\n",
        )
        tasks = memory.get_task_section()
        assert len(tasks) == 3
        active = [t for t in tasks if not t["done"]]
        assert len(active) == 2
        assert tasks[0]["priority"] == "high"
        assert tasks[0]["due"] == "2026-04-15"
        assert tasks[2]["priority"] == "low"
