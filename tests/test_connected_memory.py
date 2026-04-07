"""Tests for the Connected Memory engine."""

import pytest

from moha_mind.agent.connected_memory import ConnectedMemory
from moha_mind.agent.memory import MemoryManager


@pytest.fixture
def setup(tmp_path):
    memory = MemoryManager(memory_dir=str(tmp_path))
    memory.ensure_templates()
    connected = ConnectedMemory(memory)
    return memory, connected


class TestConnectedMemory:
    def test_birthday_connection(self, setup):
        memory, connected = setup
        actions = connected.process_new_info("My wife Sarah birthday is on 1992-03-15")
        assert len(actions) > 0
        occasions = memory.read("occasions")
        assert "Sarah" in occasions

    def test_car_service_connection(self, setup):
        memory, connected = setup
        actions = connected.process_new_info("I did an oil change for my car at Toyota")
        assert any("service" in a.lower() or "vehicle" in a.lower() for a in actions)

    def test_no_matching_rules(self, setup):
        _, connected = setup
        actions = connected.process_new_info("The weather is nice today")
        assert len(actions) == 0

    def test_gift_connection(self, setup):
        memory, connected = setup
        actions = connected.process_new_info("Gift idea: a watch for my wife")
        assert any("gift" in a.lower() for a in actions)

    def test_bill_connection(self, setup):
        memory, connected = setup
        actions = connected.process_new_info("My electricity bill is 400 SAR due next week")
        assert any("finance" in a.lower() or "bill" in a.lower() for a in actions)

    def test_get_connected_insights(self, setup):
        memory, connected = setup
        memory.write("profile", "Name: Moha\nBirthday: June 15")
        memory.write("occasions", "Birthday: June 15")
        insights = connected.get_connected_insights("birthday")
        assert len(insights) > 0
