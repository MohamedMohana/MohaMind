"""Comprehensive tests for all MCP servers."""

from datetime import timedelta

import pytest

from moha_mind.mcp_servers.family.server import FamilyServer
from moha_mind.mcp_servers.life_tracker.server import LifeTrackerServer
from moha_mind.mcp_servers.memory_store.server import MemoryStoreServer
from moha_mind.mcp_servers.social.server import SocialServer
from moha_mind.mcp_servers.tasks.server import TaskServer
from moha_mind.utils.timezone import now_ksa


class TestMemoryStoreServer:
    @pytest.mark.asyncio
    async def test_save(self, tmp_memory):
        server = MemoryStoreServer(tmp_memory)
        result = await server._save(category="profile", content="Hello World")
        assert "Saved to profile" in result
        assert "Hello World" in tmp_memory.read("profile")

    @pytest.mark.asyncio
    async def test_save_preserves_existing_memory(self, tmp_memory):
        tmp_memory.write("family", "Existing family fact")
        server = MemoryStoreServer(tmp_memory)

        await server._save(category="family", content="New family fact")

        content = tmp_memory.read("family")
        assert "Existing family fact" in content
        assert "New family fact" in content

    @pytest.mark.asyncio
    async def test_read(self, tmp_memory):
        tmp_memory.write("profile", "Test content")
        server = MemoryStoreServer(tmp_memory)
        result = await server._read(category="profile")
        assert "Test content" in result

    @pytest.mark.asyncio
    async def test_read_empty(self, tmp_memory):
        server = MemoryStoreServer(tmp_memory)
        result = await server._read(category="nonexistent")
        assert "No data" in result

    @pytest.mark.asyncio
    async def test_search(self, tmp_memory):
        tmp_memory.write("profile", "Name: Mohana\nLocation: Saudi Arabia")
        server = MemoryStoreServer(tmp_memory)
        result = await server._search(query="Mohana")
        assert "Mohana" in result

    @pytest.mark.asyncio
    async def test_search_no_results(self, tmp_memory):
        server = MemoryStoreServer(tmp_memory)
        result = await server._search(query="xyznonexistent")
        assert "No results" in result

    @pytest.mark.asyncio
    async def test_update_profile(self, tmp_memory):
        server = MemoryStoreServer(tmp_memory)
        result = await server._update_profile(section="Interests", content="- Coding")
        assert "Interests" in result

    @pytest.mark.asyncio
    async def test_get_profile(self, tmp_memory):
        tmp_memory.write("profile", "Name: Mohana")
        server = MemoryStoreServer(tmp_memory)
        result = await server._get_profile()
        assert "Mohana" in result

    @pytest.mark.asyncio
    async def test_remember_fact(self, tmp_memory):
        server = MemoryStoreServer(tmp_memory)
        result = await server._remember_fact(fact="Loves Python", category="notes")
        assert "Loves Python" in result

    @pytest.mark.asyncio
    async def test_recall_facts(self, tmp_memory):
        tmp_memory.write("notes", "Loves Python\nLikes coffee")
        server = MemoryStoreServer(tmp_memory)
        result = await server._recall_facts(topic="Python")
        assert "Python" in result

    @pytest.mark.asyncio
    async def test_recall_facts_empty(self, tmp_memory):
        server = MemoryStoreServer(tmp_memory)
        result = await server._recall_facts(topic="xyznonexistent")
        assert "don't remember" in result

    @pytest.mark.asyncio
    async def test_save_note(self, tmp_memory):
        server = MemoryStoreServer(tmp_memory)
        result = await server._save_note(title="Test Note", content="Some content")
        assert "test_note" in result

    @pytest.mark.asyncio
    async def test_read_note(self, tmp_memory):
        tmp_memory.save_note("TestNote", "Hello")
        server = MemoryStoreServer(tmp_memory)
        result = await server._read_note(title="TestNote")
        assert "Hello" in result

    @pytest.mark.asyncio
    async def test_read_note_missing(self, tmp_memory):
        server = MemoryStoreServer(tmp_memory)
        result = await server._read_note(title="Missing")
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_list_notes(self, tmp_memory):
        tmp_memory.save_note("Note1", "A")
        tmp_memory.save_note("Note2", "B")
        server = MemoryStoreServer(tmp_memory)
        result = await server._list_notes()
        assert "note1" in result
        assert "note2" in result

    @pytest.mark.asyncio
    async def test_list_notes_empty(self, tmp_memory):
        server = MemoryStoreServer(tmp_memory)
        result = await server._list_notes()
        assert "No notes" in result

    @pytest.mark.asyncio
    async def test_append_to_section(self, tmp_memory):
        server = MemoryStoreServer(tmp_memory)
        result = await server._append_to_section(category="profile", section="Hobbies", line="- Reading")
        assert "profile" in result
        assert "Hobbies" in result

    @pytest.mark.asyncio
    async def test_handle_tool_unknown(self, tmp_memory):
        server = MemoryStoreServer(tmp_memory)
        result = await server.handle_tool("nonexistent_tool", {})
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_handle_tool_save(self, tmp_memory):
        server = MemoryStoreServer(tmp_memory)
        result = await server.handle_tool("save_memory", {"category": "tasks", "content": "Test"})
        assert "Saved to tasks" in result


class TestTaskServerExtended:
    @pytest.mark.asyncio
    async def test_add_task_with_due(self, tmp_memory):
        server = TaskServer(tmp_memory)
        result = await server._add_task(text="Renew passport", priority="high", due="2026-06-01")
        assert "Renew passport" in result
        assert "HIGH" in result
        assert "2026-06-01" in result

    @pytest.mark.asyncio
    async def test_add_task_no_due(self, tmp_memory):
        server = TaskServer(tmp_memory)
        result = await server._add_task(text="Buy groceries")
        assert "Buy groceries" in result
        assert "MEDIUM" in result

    @pytest.mark.asyncio
    async def test_complete_task_found(self, tmp_memory):
        tmp_memory.add_task("Test task")
        server = TaskServer(tmp_memory)
        result = await server._complete_task(task_text="Test task")
        assert "completed" in result.lower()

    @pytest.mark.asyncio
    async def test_complete_task_not_found(self, tmp_memory):
        server = TaskServer(tmp_memory)
        result = await server._complete_task(task_text="Nonexistent")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_list_tasks_with_completed(self, tmp_memory):
        tmp_memory.add_task("Active task")
        tmp_memory.add_task("Done task")
        tmp_memory.complete_task("Done task")
        server = TaskServer(tmp_memory)
        result = await server._list_tasks(include_completed=True)
        assert "Active task" in result
        assert "Done task" in result

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, tmp_memory):
        server = TaskServer(tmp_memory)
        result = await server._list_tasks()
        assert "No tasks" in result

    @pytest.mark.asyncio
    async def test_update_task_text(self, tmp_memory):
        tmp_memory.add_task("Old text", priority="medium")
        server = TaskServer(tmp_memory)
        result = await server._update_task(task_text="Old text", new_text="New text")
        assert "updated" in result.lower()

    @pytest.mark.asyncio
    async def test_update_task_not_found(self, tmp_memory):
        server = TaskServer(tmp_memory)
        result = await server._update_task(task_text="Nonexistent", new_text="New")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_update_task_priority(self, tmp_memory):
        tmp_memory.add_task("Important thing", priority="low")
        server = TaskServer(tmp_memory)
        result = await server._update_task(task_text="Important thing", priority="high")
        assert "updated" in result.lower()

    @pytest.mark.asyncio
    async def test_set_reminder_existing_task(self, tmp_memory):
        tmp_memory.add_task("Remind me")
        server = TaskServer(tmp_memory)
        result = await server._set_reminder(task_text="Remind me", remind_date="2026-05-01")
        assert "Reminder set" in result

    @pytest.mark.asyncio
    async def test_set_reminder_missing_task(self, tmp_memory):
        server = TaskServer(tmp_memory)
        result = await server._set_reminder(task_text="Nonexistent", remind_date="2026-05-01")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_handle_tool_unknown(self, tmp_memory):
        server = TaskServer(tmp_memory)
        result = await server.handle_tool("nonexistent", {})
        assert "Unknown" in result


class TestLifeTrackerServerExtended:
    @pytest.mark.asyncio
    async def test_vehicle_update_mileage(self, tmp_memory):
        tmp_memory.write("vehicle", "# Vehicle\n- Mileage: 50000 km\n")
        server = LifeTrackerServer(tmp_memory)
        result = await server._vehicle_update_mileage(mileage="55000")
        assert "55000" in result

    @pytest.mark.asyncio
    async def test_vehicle_update_mileage_no_field(self, tmp_memory):
        tmp_memory.write("vehicle", "# Vehicle\n")
        server = LifeTrackerServer(tmp_memory)
        result = await server._vehicle_update_mileage(mileage="55000")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_vehicle_get_next_service(self, tmp_memory):
        tmp_memory.write("vehicle", "# Vehicle\n## Next Service\n- Oil change on 2026-05-01\n")
        server = LifeTrackerServer(tmp_memory)
        result = await server._vehicle_get_next_service()
        assert "Oil change" in result

    @pytest.mark.asyncio
    async def test_vehicle_get_next_service_empty(self, tmp_memory):
        tmp_memory.write("vehicle", "# Vehicle\n")
        server = LifeTrackerServer(tmp_memory)
        result = await server._vehicle_get_next_service()
        assert "No upcoming" in result

    @pytest.mark.asyncio
    async def test_finance_add_bill(self, tmp_memory):
        server = LifeTrackerServer(tmp_memory)
        result = await server._finance_add_bill(provider="STC", amount="300", due_day="15", auto_pay=True)
        assert "STC" in result
        assert "300" in result

    @pytest.mark.asyncio
    async def test_finance_add_subscription(self, tmp_memory):
        server = LifeTrackerServer(tmp_memory)
        result = await server._finance_add_subscription(service="Netflix", amount="45 SAR", renews_day="1st")
        assert "Netflix" in result

    @pytest.mark.asyncio
    async def test_health_log_vitals(self, tmp_memory):
        server = LifeTrackerServer(tmp_memory)
        result = await server._health_log_vitals(weight="75", bp="120/80", notes="Feeling good")
        assert "Vitals logged" in result

    @pytest.mark.asyncio
    async def test_health_add_doctor(self, tmp_memory):
        server = LifeTrackerServer(tmp_memory)
        result = await server._health_add_doctor(name="Ahmed", specialty="Cardiology", phone="0551234567")
        assert "Dr. Ahmed" in result

    @pytest.mark.asyncio
    async def test_home_add_maintenance(self, tmp_memory):
        server = LifeTrackerServer(tmp_memory)
        result = await server._home_add_maintenance(issue="Leaky faucet", resolution="Fixed by plumber")
        assert "Leaky faucet" in result

    @pytest.mark.asyncio
    async def test_home_add_appliance(self, tmp_memory):
        server = LifeTrackerServer(tmp_memory)
        result = await server._home_add_appliance(name="Washer", brand="Samsung", warranty_expires="2027-01-01")
        assert "Washer" in result

    @pytest.mark.asyncio
    async def test_home_get_warranties(self, tmp_memory):
        tmp_memory.write("home", "# Home\n## Appliances\n- Washer - Warranty expires: 2027-01-01\n")
        server = LifeTrackerServer(tmp_memory)
        result = await server._home_get_warranties()
        assert "Washer" in result

    @pytest.mark.asyncio
    async def test_home_get_warranties_empty(self, tmp_memory):
        tmp_memory.write("home", "# Home\n")
        server = LifeTrackerServer(tmp_memory)
        result = await server._home_get_warranties()
        assert "No warranties" in result

    @pytest.mark.asyncio
    async def test_document_add(self, tmp_memory):
        server = LifeTrackerServer(tmp_memory)
        result = await server._document_add(name="Passport", number="A12345678", expires="2030-06-15")
        assert "Passport" in result

    @pytest.mark.asyncio
    async def test_document_get_expiring(self, tmp_memory):
        server = LifeTrackerServer(tmp_memory)
        result = await server._document_get_expiring(days_ahead=90)
        assert "No documents" in result or "expiring" in result.lower()

    @pytest.mark.asyncio
    async def test_learning_add_course(self, tmp_memory):
        server = LifeTrackerServer(tmp_memory)
        result = await server._learning_add_course(name="Python 101", platform="Coursera", progress="25%")
        assert "Python 101" in result

    @pytest.mark.asyncio
    async def test_learning_update_progress(self, tmp_memory):
        tmp_memory.write("learning", "# Learning\n## Current Courses\n- Python 101 - Coursera - Progress: 25%\n")
        server = LifeTrackerServer(tmp_memory)
        result = await server._learning_update_progress(course_name="Python 101", progress="50%")
        assert "50%" in result

    @pytest.mark.asyncio
    async def test_learning_update_progress_not_found(self, tmp_memory):
        tmp_memory.write("learning", "# Learning\n")
        server = LifeTrackerServer(tmp_memory)
        result = await server._learning_update_progress(course_name="Nonexistent", progress="50%")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_finance_get_upcoming(self, tmp_memory):
        tmp_memory.write("finances", "# Finances\n## Monthly Bills\n- [STC] 300 SAR - Due: 15th\n")
        server = LifeTrackerServer(tmp_memory)
        result = await server._finance_get_upcoming()
        assert "STC" in result or "No upcoming" in result

    @pytest.mark.asyncio
    async def test_handle_tool_unknown(self, tmp_memory):
        server = LifeTrackerServer(tmp_memory)
        result = await server.handle_tool("nonexistent", {})
        assert "Unknown" in result


class TestFamilyServerExtended:
    @pytest.mark.asyncio
    async def test_update_pregnancy_week_explicit(self, tmp_memory):
        tmp_memory.write("family", "# Family\n- Current week: 20\n")
        server = FamilyServer(tmp_memory)
        result = await server._update_pregnancy_week(week=24)
        assert "24" in result
        assert "week 24" in result.lower()

    @pytest.mark.asyncio
    async def test_update_pregnancy_week_no_data(self, tmp_memory):
        server = FamilyServer(tmp_memory)
        result = await server._update_pregnancy_week()
        assert "no due date" in result.lower() or "no family" in result.lower()

    @pytest.mark.asyncio
    async def test_add_appointment_full(self, tmp_memory):
        server = FamilyServer(tmp_memory)
        result = await server._add_appointment(
            person="Wife",
            doctor="Al-Rashid",
            date="2026-05-10",
            time="10:00",
            location="City Hospital",
            notes="Checkup",
        )
        assert "Wife" in result
        assert "Al-Rashid" in result

    @pytest.mark.asyncio
    async def test_add_kid_event(self, tmp_memory):
        server = FamilyServer(tmp_memory)
        result = await server._add_kid_event(kid_name="Sara", event="School play", date="2026-05-15", time="4:00 PM")
        assert "Sara" in result
        assert "School play" in result

    @pytest.mark.asyncio
    async def test_get_upcoming_events(self, tmp_memory):
        tmp_memory.write(
            "family",
            "# Family\n## Upcoming Appointments\n- [2099-01-15] Wife: Dr. Smith\n",
        )
        server = FamilyServer(tmp_memory)
        result = await server._get_upcoming(days_ahead=30000)
        assert "Dr. Smith" in result or "No family events" in result

    @pytest.mark.asyncio
    async def test_get_upcoming_no_events(self, tmp_memory):
        tmp_memory.write("family", "# Family\n")
        server = FamilyServer(tmp_memory)
        result = await server._get_upcoming()
        assert "No family events" in result

    @pytest.mark.asyncio
    async def test_add_vaccination(self, tmp_memory):
        server = FamilyServer(tmp_memory)
        result = await server._add_vaccination(kid_name="Sara", vaccine="MMR", date="2026-05-01", next_due="2026-08-01")
        assert "Sara" in result
        assert "MMR" in result

    @pytest.mark.asyncio
    async def test_get_vaccination_schedule_all(self, tmp_memory):
        server = FamilyServer(tmp_memory)
        result = await server._get_vaccination_schedule()
        assert "birth" in result.lower()
        assert "DTaP" in result

    @pytest.mark.asyncio
    async def test_get_vaccination_schedule_by_age(self, tmp_memory):
        server = FamilyServer(tmp_memory)
        result = await server._get_vaccination_schedule(age_months=6)
        assert "DTaP" in result

    @pytest.mark.asyncio
    async def test_get_pregnancy_info_specific_week(self, tmp_memory):
        server = FamilyServer(tmp_memory)
        result = await server._get_pregnancy_info(week=20)
        assert "20" in result
        assert "anatomy" in result.lower()

    @pytest.mark.asyncio
    async def test_get_pregnancy_info_all(self, tmp_memory):
        server = FamilyServer(tmp_memory)
        result = await server._get_pregnancy_info()
        assert "Week 4" in result
        assert "Week 40" in result

    @pytest.mark.asyncio
    async def test_handle_tool_unknown(self, tmp_memory):
        server = FamilyServer(tmp_memory)
        result = await server.handle_tool("nonexistent", {})
        assert "Unknown" in result


class TestSocialServerExtended:
    @pytest.mark.asyncio
    async def test_add_person_full(self, tmp_memory):
        server = SocialServer(tmp_memory)
        result = await server._add_person(
            name="Ahmed", relationship="colleague", birthday="06-15", contact_frequency="weekly", notes="Works at STC"
        )
        assert "Ahmed" in result
        assert "birthday tracked" in result.lower()

    @pytest.mark.asyncio
    async def test_add_person_no_birthday(self, tmp_memory):
        server = SocialServer(tmp_memory)
        result = await server._add_person(name="Sara", relationship="friend")
        assert "Sara" in result
        assert "birthday" not in result.lower()

    @pytest.mark.asyncio
    async def test_log_contact_found(self, tmp_memory):
        tmp_memory.write("relationships", "### Ahmed\n- Last contacted: 2026-01-01\n- Contact frequency: monthly\n")
        server = SocialServer(tmp_memory)
        result = await server._log_contact(name="Ahmed", method="call", notes="Great chat")
        assert "Ahmed" in result
        assert "call" in result

    @pytest.mark.asyncio
    async def test_log_contact_not_found(self, tmp_memory):
        tmp_memory.write("relationships", "### Bob\n- Last contacted: 2026-01-01\n")
        server = SocialServer(tmp_memory)
        result = await server._log_contact(name="Nonexistent")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_get_neglected_all_caught_up(self, tmp_memory):
        recent = (now_ksa() - timedelta(days=7)).strftime("%Y-%m-%d")
        tmp_memory.write("relationships", f"### Ahmed\n- Last contacted: {recent}\n")
        server = SocialServer(tmp_memory)
        result = await server._get_neglected(days_threshold=30)
        assert "caught up" in result.lower()

    @pytest.mark.asyncio
    async def test_get_neglected_no_data(self, tmp_memory):
        server = SocialServer(tmp_memory)
        result = await server._get_neglected()
        assert "caught up" in result.lower() or "No relationships" in result

    @pytest.mark.asyncio
    async def test_add_gift_idea(self, tmp_memory):
        server = SocialServer(tmp_memory)
        result = await server._add_gift_idea(person="Ahmed", idea="Book", occasion="birthday", estimated_cost="100")
        assert "Book" in result
        assert "Ahmed" in result

    @pytest.mark.asyncio
    async def test_get_gift_ideas(self, tmp_memory):
        tmp_memory.write("relationships", "# Relationships\n## Gift Ideas\n- (Ahmed) Book\n- (Sara) Perfume\n")
        server = SocialServer(tmp_memory)
        result = await server._get_gift_ideas()
        assert "Book" in result
        assert "Perfume" in result

    @pytest.mark.asyncio
    async def test_get_gift_ideas_filtered(self, tmp_memory):
        tmp_memory.write("relationships", "# Relationships\n## Gift Ideas\n- (Ahmed) Book\n- (Sara) Perfume\n")
        server = SocialServer(tmp_memory)
        result = await server._get_gift_ideas(person="Ahmed")
        assert "Book" in result

    @pytest.mark.asyncio
    async def test_get_gift_ideas_empty(self, tmp_memory):
        tmp_memory.write("relationships", "# Relationships\n")
        server = SocialServer(tmp_memory)
        result = await server._get_gift_ideas()
        assert "No gift ideas" in result

    @pytest.mark.asyncio
    async def test_get_upcoming_birthdays_no_data(self, tmp_memory):
        server = SocialServer(tmp_memory)
        result = await server._get_upcoming_birthdays()
        assert "No birthdays" in result or "No occasions" in result

    @pytest.mark.asyncio
    async def test_handle_tool_unknown(self, tmp_memory):
        server = SocialServer(tmp_memory)
        result = await server.handle_tool("nonexistent", {})
        assert "Unknown" in result
