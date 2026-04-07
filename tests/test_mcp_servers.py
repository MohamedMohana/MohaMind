"""Tests for MCP servers."""

import pytest

from moha_mind.agent.memory import MemoryManager
from moha_mind.mcp_servers.family.server import FamilyServer
from moha_mind.mcp_servers.life_tracker.server import LifeTrackerServer
from moha_mind.mcp_servers.social.server import SocialServer
from moha_mind.mcp_servers.tasks.server import TaskServer


@pytest.fixture
def memory(tmp_path):
    m = MemoryManager(memory_dir=str(tmp_path))
    m.ensure_templates()
    return m


class TestTaskServer:
    @pytest.mark.asyncio
    async def test_add_task(self, memory):
        server = TaskServer(memory)
        result = await server.handle_tool("add_task", {"text": "Test task", "priority": "high"})
        assert "Test task" in result
        tasks = memory.get_task_section()
        assert any("Test task" in t["text"] for t in tasks)

    @pytest.mark.asyncio
    async def test_complete_task(self, memory):
        memory.write("tasks", "# Tasks\n\n## Active\n- [ ] Test task\n")
        server = TaskServer(memory)
        result = await server.handle_tool("complete_task", {"task_text": "Test task"})
        assert "completed" in result.lower()

    @pytest.mark.asyncio
    async def test_list_tasks(self, memory):
        memory.write("tasks", "# Tasks\n\n## Active\n- [ ] Task A\n- [ ] Task B\n")
        server = TaskServer(memory)
        result = await server.handle_tool("list_tasks", {})
        assert "Task A" in result
        assert "Task B" in result

    @pytest.mark.asyncio
    async def test_unknown_tool(self, memory):
        server = TaskServer(memory)
        result = await server.handle_tool("nonexistent", {})
        assert "Unknown" in result


class TestLifeTrackerServer:
    @pytest.mark.asyncio
    async def test_vehicle_add_service(self, memory):
        server = LifeTrackerServer(memory)
        result = await server.handle_tool(
            "vehicle_add_service",
            {
                "service_type": "oil change",
                "location": "Toyota dealer",
                "mileage": "45000",
            },
        )
        assert "oil change" in result
        content = memory.read("vehicle")
        assert "oil change" in content.lower()

    @pytest.mark.asyncio
    async def test_finance_add_bill(self, memory):
        server = LifeTrackerServer(memory)
        result = await server.handle_tool(
            "finance_add_bill",
            {
                "provider": "STC",
                "amount": "300",
                "due_day": "15th",
            },
        )
        assert "STC" in result
        content = memory.read("finances")
        assert "STC" in content

    @pytest.mark.asyncio
    async def test_health_add_medication(self, memory):
        server = LifeTrackerServer(memory)
        result = await server.handle_tool(
            "health_add_medication",
            {
                "name": "Vitamin D",
                "dosage": "1000 IU",
                "frequency": "daily",
            },
        )
        assert "Vitamin D" in result

    @pytest.mark.asyncio
    async def test_document_add(self, memory):
        server = LifeTrackerServer(memory)
        result = await server.handle_tool(
            "document_add",
            {
                "name": "Passport",
                "number": "AB1234567",
                "expires": "2030-06-15",
            },
        )
        assert "Passport" in result


class TestFamilyServer:
    @pytest.mark.asyncio
    async def test_update_pregnancy_week(self, memory):
        server = FamilyServer(memory)
        memory.write("family", "# Family\n\n## Pregnancy Tracker\n- Due date: 2026-10-20\n- Current week: 20\n")
        result = await server.handle_tool("family_update_pregnancy_week", {"week": 24})
        assert "24" in result

    @pytest.mark.asyncio
    async def test_add_appointment(self, memory):
        server = FamilyServer(memory)
        result = await server.handle_tool(
            "family_add_appointment",
            {
                "person": "Wife",
                "doctor": "Ahmed",
                "date": "2026-04-15",
                "time": "10:00",
            },
        )
        assert "appointment" in result.lower() or "Wife" in result

    @pytest.mark.asyncio
    async def test_vaccination_schedule(self, memory):
        server = FamilyServer(memory)
        result = await server.handle_tool("family_get_vaccination_schedule", {})
        assert "DTaP" in result or "Hepatitis" in result


class TestSocialServer:
    @pytest.mark.asyncio
    async def test_add_person(self, memory):
        server = SocialServer(memory)
        result = await server.handle_tool(
            "social_add_person",
            {
                "name": "Ahmed",
                "relationship": "close friend",
                "birthday": "1990-07-20",
                "contact_frequency": "weekly",
            },
        )
        assert "Ahmed" in result
        occasions = memory.read("occasions")
        assert "Ahmed" in occasions

    @pytest.mark.asyncio
    async def test_add_gift_idea(self, memory):
        server = SocialServer(memory)
        result = await server.handle_tool(
            "social_add_gift_idea",
            {
                "person": "wife",
                "idea": "Perfume set",
                "occasion": "birthday",
            },
        )
        assert "gift" in result.lower() or "saved" in result.lower()
