"""Tests for the memory deletion helpers."""


class TestDeleteLine:
    def test_delete_line_removes_specific_line(self, tmp_memory):
        tmp_memory.write("tasks", "# Tasks\n\n- [ ] Task A\n- [ ] Task B\n- [ ] Task C\n")
        ok = tmp_memory.delete_line("tasks", line_number=4)
        assert ok
        content = tmp_memory.read("tasks")
        assert "Task B" not in content
        assert "Task A" in content
        assert "Task C" in content

    def test_delete_line_out_of_range_returns_false(self, tmp_memory):
        tmp_memory.write("tasks", "# Tasks\n- [ ] Task A\n")
        assert tmp_memory.delete_line("tasks", line_number=99) is False

    def test_delete_line_empty_category_returns_false(self, tmp_memory):
        assert tmp_memory.delete_line("nonexistent_cat", 1) is False


class TestDeleteMatches:
    def test_deletes_matching_lines(self, tmp_memory):
        tmp_memory.write(
            "finances",
            "# Finances\n\n## Subscriptions\n- Netflix 40 SAR\n- Spotify 20 SAR\n- Shahid 30 SAR\n",
        )
        removed = tmp_memory.delete_matches("finances", "Spotify")
        assert removed == 1
        content = tmp_memory.read("finances")
        assert "Spotify" not in content
        assert "Netflix" in content

    def test_delete_matches_ignores_comments_and_headers(self, tmp_memory):
        tmp_memory.write("tasks", "# Tasks\n<!-- note about tasks -->\n- [ ] tasks real item\n")
        removed = tmp_memory.delete_matches("tasks", "tasks")
        assert removed == 1
        content = tmp_memory.read("tasks")
        assert "# Tasks" in content
        assert "<!-- note about tasks -->" in content
        assert "tasks real item" not in content

    def test_delete_matches_respects_max_deletions(self, tmp_memory):
        tmp_memory.write("tasks", "- [ ] Call A\n- [ ] Call B\n- [ ] Call C\n")
        removed = tmp_memory.delete_matches("tasks", "Call", max_deletions=2)
        assert removed == 2
        content = tmp_memory.read("tasks")
        assert content.count("Call") == 1

    def test_delete_matches_no_hits_returns_zero(self, tmp_memory):
        tmp_memory.write("tasks", "- [ ] foo\n")
        removed = tmp_memory.delete_matches("tasks", "nonexistent")
        assert removed == 0

    def test_delete_matches_empty_query_returns_zero(self, tmp_memory):
        tmp_memory.write("tasks", "- [ ] foo\n")
        assert tmp_memory.delete_matches("tasks", "   ") == 0


class TestDeleteNote:
    def test_delete_note_removes_file(self, tmp_memory):
        path = tmp_memory.save_note("My Note", "Hello")
        assert path.exists()
        ok = tmp_memory.delete_note("My Note")
        assert ok
        assert not path.exists()

    def test_delete_note_missing_returns_false(self, tmp_memory):
        assert tmp_memory.delete_note("does-not-exist") is False
