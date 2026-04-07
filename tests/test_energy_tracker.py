"""Tests for the energy tracker."""

import pytest

from moha_mind.agent.energy_tracker import EnergyTracker
from moha_mind.agent.memory import MemoryManager


@pytest.fixture
def tracker(tmp_path):
    memory = MemoryManager(memory_dir=str(tmp_path))
    return EnergyTracker(memory)


class TestMoodDetection:
    def test_high_energy_great(self, tracker):
        assert tracker.analyze_message_mood("I'm feeling great today!") == "high"

    def test_high_energy_excited(self, tracker):
        assert tracker.analyze_message_mood("So excited about the new project!") == "high"

    def test_high_energy_amazing(self, tracker):
        assert tracker.analyze_message_mood("That's amazing news") == "high"

    def test_high_energy_motivated(self, tracker):
        assert tracker.analyze_message_mood("I feel motivated to work") == "high"

    def test_high_energy_happy(self, tracker):
        assert tracker.analyze_message_mood("I'm so happy right now") == "high"

    def test_low_energy_tired(self, tracker):
        assert tracker.analyze_message_mood("I'm so tired today") == "low"

    def test_low_energy_stressed(self, tracker):
        assert tracker.analyze_message_mood("Work is so stressed lately") == "low"

    def test_low_energy_sick(self, tracker):
        assert tracker.analyze_message_mood("I feel sick") == "low"

    def test_low_energy_exhausted(self, tracker):
        assert tracker.analyze_message_mood("Completely exhausted after the trip") == "low"

    def test_low_energy_sad(self, tracker):
        assert tracker.analyze_message_mood("Feeling sad about the news") == "low"

    def test_neutral_message(self, tracker):
        assert tracker.analyze_message_mood("What's the weather like?") == "neutral"

    def test_neutral_short(self, tracker):
        assert tracker.analyze_message_mood("ok") == "neutral"

    def test_mixed_high_and_low(self, tracker):
        result = tracker.analyze_message_mood("I'm excited but also stressed")
        assert result == "neutral"

    def test_more_high_than_low(self, tracker):
        result = tracker.analyze_message_mood("Great day, happy and motivated, but a bit busy")
        assert result == "high"

    def test_more_low_than_high(self, tracker):
        result = tracker.analyze_message_mood("Tired, stressed, and overwhelmed with work")
        assert result == "low"

    def test_empty_message(self, tracker):
        assert tracker.analyze_message_mood("") == "neutral"


class TestLogInteraction:
    def test_log_creates_entry(self, tracker):
        tracker.log_interaction("Hello there!", 50)
        content = tracker.memory.read("energy_log")
        assert "Mood: neutral" in content
        assert "Message length: 12" in content
        assert "Response length: 50" in content

    def test_log_with_high_mood(self, tracker):
        tracker.log_interaction("I'm feeling great!", 100)
        content = tracker.memory.read("energy_log")
        assert "Mood: high" in content

    def test_log_with_low_mood(self, tracker):
        tracker.log_interaction("I'm so tired", 0)
        content = tracker.memory.read("energy_log")
        assert "Mood: low" in content

    def test_multiple_logs(self, tracker):
        tracker.log_interaction("First message", 10)
        tracker.log_interaction("Second message", 20)
        content = tracker.memory.read("energy_log")
        assert content.count("Mood:") == 2


class TestGetProductiveHours:
    def test_default_when_empty(self, tracker):
        result = tracker.get_productive_hours()
        assert result == [9, 10, 11]

    def test_default_when_no_mood_data(self, tracker):
        tracker.memory.write("energy_log", "# Energy Log\nSome random text without mood data\n")
        result = tracker.get_productive_hours()
        assert result == [9, 10, 11]

    def test_with_data(self, tracker):
        tracker.memory.write(
            "energy_log",
            "# Energy Log\n\n## Raw Data\n"
            "- [2026-04-07 9:00] Mood: high | Message length: 10 | Response length: 50\n"
            "- [2026-04-07 14:00] Mood: low | Message length: 5 | Response length: 20\n"
            "- [2026-04-07 10:00] Mood: high | Message length: 15 | Response length: 80\n",
        )
        result = tracker.get_productive_hours()
        assert 9 in result
        assert 10 in result
        assert len(result) == 3

    def test_returns_top_three(self, tracker):
        tracker.memory.write(
            "energy_log",
            "# Energy Log\n\n## Raw Data\n"
            "- [2026-04-07 9:00] Mood: high\n"
            "- [2026-04-07 10:00] Mood: high\n"
            "- [2026-04-07 11:00] Mood: high\n"
            "- [2026-04-07 14:00] Mood: low\n"
            "- [2026-04-07 15:00] Mood: low\n",
        )
        result = tracker.get_productive_hours()
        assert len(result) == 3


class TestGetEnergySuggestion:
    def test_returns_string(self, tracker):
        result = tracker.get_energy_suggestion()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_productive_hour_suggestion(self, tracker):
        tracker.memory.write(
            "energy_log",
            "# Energy Log\n\n## Raw Data\n"
            "- [2026-04-07 9:00] Mood: high\n"
            "- [2026-04-07 10:00] Mood: high\n"
            "- [2026-04-07 11:00] Mood: high\n",
        )
        result = tracker.get_energy_suggestion()
        assert isinstance(result, str)
