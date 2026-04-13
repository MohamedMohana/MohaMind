from moha_mind.agent.session_store import SessionStore


class TestSessionStore:
    def test_append_and_load_recent_messages(self, tmp_path):
        store = SessionStore(tmp_path)
        store.append_message("cli", "user", "hello")
        store.append_message("cli", "assistant", "hi there")

        messages = store.load_recent_messages("cli")

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["content"] == "hi there"

    def test_search_messages(self, tmp_path):
        store = SessionStore(tmp_path)
        store.append_message("cli", "user", "Need to renew my passport soon")
        store.append_message("other", "user", "Buy groceries")

        results = store.search_messages("passport", chat_id="cli")

        assert len(results) == 1
        assert results[0]["chat_id"] == "cli"
        assert "passport" in results[0]["content"].lower()

    def test_count_messages(self, tmp_path):
        store = SessionStore(tmp_path)
        store.append_message("cli", "user", "one")
        store.append_message("cli", "assistant", "two")
        store.append_message("telegram", "user", "three")

        assert store.count_messages() == 3
        assert store.count_messages("cli") == 2

    def test_append_message_ignores_blank_content(self, tmp_path):
        store = SessionStore(tmp_path)
        store.append_message("cli", "user", "   ")
        assert store.count_messages() == 0
