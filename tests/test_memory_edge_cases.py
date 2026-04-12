"""Comprehensive tests for memory manager edge cases."""

from moha_mind.agent.memory import MemoryManager


class TestMemoryEdgeCases:
    def test_write_and_read_cycle(self, tmp_memory):
        tmp_memory.write("profile", "Hello")
        assert "Hello" in tmp_memory.read("profile")

    def test_overwrite(self, tmp_memory):
        tmp_memory.write("profile", "First")
        tmp_memory.write("profile", "Second")
        content = tmp_memory.read("profile")
        assert "Second" in content
        assert "First" not in content

    def test_read_nonexistent(self, tmp_memory):
        result = tmp_memory.read("nonexistent_category")
        assert result == ""

    def test_append_to_existing_content(self, tmp_memory):
        tmp_memory.write("profile", "# Profile\n## Name\n- Mohana")
        tmp_memory.append("profile", "\n## Notes\n- Test")
        content = tmp_memory.read("profile")
        assert "Mohana" in content
        assert "Test" in content

    def test_append_to_section_existing(self, tmp_memory):
        tmp_memory.write("profile", "# Profile\n## Hobbies\n- Reading\n")
        tmp_memory.append_to_section("profile", "Hobbies", "- Coding")
        content = tmp_memory.read("profile")
        assert "Reading" in content
        assert "Coding" in content

    def test_append_to_section_new(self, tmp_memory):
        tmp_memory.write("profile", "# Profile\n")
        tmp_memory.append_to_section("profile", "New Section", "- Item 1")
        content = tmp_memory.read("profile")
        assert "New Section" in content
        assert "Item 1" in content

    def test_search_specific_categories(self, tmp_memory):
        tmp_memory.write("profile", "Name: Mohana")
        tmp_memory.write("tasks", "- [ ] Fix bug")
        results = tmp_memory.search("Mohana", categories=["profile"])
        assert len(results) >= 1
        assert all(r["category"] == "profile" for r in results)

    def test_search_empty_query(self, tmp_memory):
        results = tmp_memory.search("xyznonexistent12345")
        assert results == []

    def test_get_all_context(self, tmp_memory):
        tmp_memory.write("profile", "Name: Mohana")
        tmp_memory.write("tasks", "- [ ] Task")
        context = tmp_memory.get_all_context()
        assert "Mohana" in context
        assert "Task" in context

    def test_save_daily_log(self, tmp_memory):
        tmp_memory.save_daily_log("Test log entry")

        daily_dir = tmp_memory.memory_path / "daily_log"
        assert daily_dir.exists()
        files = list(daily_dir.glob("*.md"))
        assert len(files) >= 1

    def test_complete_task_not_found(self, tmp_memory):
        result = tmp_memory.complete_task("Nonexistent task")
        assert result is False

    def test_get_task_section_with_due(self, tmp_memory):
        tmp_memory.add_task("Task with due", priority="high", due="2026-06-01")
        tasks = tmp_memory.get_task_section()
        assert len(tasks) == 1
        assert tasks[0]["due"] == "2026-06-01"
        assert tasks[0]["priority"] == "high"

    def test_get_task_section_empty(self, tmp_memory):
        tmp_memory.write("tasks", "# Tasks\n")
        tasks = tmp_memory.get_task_section()
        assert tasks == []

    def test_get_expiring_items_none(self, tmp_memory):
        items = tmp_memory.get_expiring_items(days_ahead=90)
        assert items == []

    def test_ensure_templates_creates_files(self, tmp_path):
        memory = MemoryManager(memory_dir=str(tmp_path))
        memory.ensure_templates()

        assert (tmp_path / "profile.md").exists()
        assert (tmp_path / "tasks.md").exists()
        assert (tmp_path / "reminders.md").exists()
        assert (tmp_path / "family.md").exists()

    def test_list_notes_empty(self, tmp_memory):
        notes = tmp_memory.list_notes()
        assert notes == []

    def test_read_note_nonexistent(self, tmp_memory):
        result = tmp_memory.read_note("nonexistent_xyz")
        assert result is None or result == ""

    def test_save_note_special_chars(self, tmp_memory):
        path = tmp_memory.save_note("TestNote", "Content here")
        assert path is not None
        content = tmp_memory.read_note("TestNote")
        assert "Content here" in content

    def test_add_task_low_priority(self, tmp_memory):
        tmp_memory.add_task("Low task", priority="low")
        tasks = tmp_memory.get_task_section()
        assert len(tasks) == 1
        assert tasks[0]["priority"] == "low"

    def test_add_task_default_priority(self, tmp_memory):
        tmp_memory.add_task("Default task")
        tasks = tmp_memory.get_task_section()
        assert tasks[0]["priority"] == "medium"
