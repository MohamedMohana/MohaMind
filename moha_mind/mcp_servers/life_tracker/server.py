"""Life Tracker MCP Server - vehicle, finance, health, home, documents."""

import re
from typing import Optional

from moha_mind.agent.memory import MemoryManager
from moha_mind.utils.timezone import ksa_today_str, now_ksa


class LifeTrackerServer:
    def __init__(self, memory: MemoryManager):
        self.memory = memory

    async def handle_tool(self, tool_name: str, arguments: dict) -> str:
        handlers = {
            "vehicle_add_service": self._vehicle_add_service,
            "vehicle_get_next_service": self._vehicle_get_next_service,
            "vehicle_update_mileage": self._vehicle_update_mileage,
            "finance_add_bill": self._finance_add_bill,
            "finance_get_upcoming": self._finance_get_upcoming,
            "finance_add_subscription": self._finance_add_subscription,
            "health_add_medication": self._health_add_medication,
            "health_log_vitals": self._health_log_vitals,
            "health_add_doctor": self._health_add_doctor,
            "home_add_maintenance": self._home_add_maintenance,
            "home_get_warranties": self._home_get_warranties,
            "home_add_appliance": self._home_add_appliance,
            "document_add": self._document_add,
            "document_get_expiring": self._document_get_expiring,
            "learning_add_course": self._learning_add_course,
            "learning_update_progress": self._learning_update_progress,
            "get_expiring_items": self._get_expiring_items,
            "log_service": self._vehicle_add_service,
        }
        handler = handlers.get(tool_name)
        if handler:
            return await handler(**arguments)
        return f"Unknown tool: {tool_name}"

    async def _vehicle_add_service(
        self, service_type: str, location: str = "", mileage: str = "", cost: str = "", date: Optional[str] = None
    ) -> str:
        service_date = date or ksa_today_str()
        mileage_str = f" - {mileage} km" if mileage else ""
        cost_str = f" - {cost} SAR" if cost else ""
        entry = f"- [{service_date}] {service_type} - {location}{mileage_str}{cost_str}".rstrip(" -")
        self.memory.append_to_section("vehicle", "Service History", entry)
        return f"Service logged: {service_type} on {service_date}"

    async def _vehicle_get_next_service(self) -> str:
        content = self.memory.read("vehicle")
        if "## Next Service" not in content:
            return "No upcoming service scheduled"
        lines = content.split("\n")
        in_section = False
        service_lines = []
        for line in lines:
            if "## Next Service" in line:
                in_section = True
                continue
            if in_section and line.startswith("##"):
                break
            if in_section and line.strip():
                service_lines.append(line.strip())
        return "\n".join(service_lines) if service_lines else "No upcoming service scheduled"

    async def _vehicle_update_mileage(self, mileage: str) -> str:
        content = self.memory.read("vehicle")
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "Mileage:" in line:
                lines[i] = f"- Mileage: {mileage} km (updated {ksa_today_str()})"
                self.memory.write("vehicle", "\n".join(lines))
                return f"Mileage updated to {mileage} km"
        return "Mileage field not found in vehicle data"

    async def _finance_add_bill(self, provider: str, amount: str, due_day: str, auto_pay: bool = False) -> str:
        auto_str = " - Auto-pay: Yes" if auto_pay else " - Auto-pay: No"
        entry = f"- [{provider}] {amount} SAR - Due: {due_day}{auto_str}"
        self.memory.append_to_section("finances", "Monthly Bills", entry)
        return f"Bill added: {provider} ({amount} SAR, due {due_day})"

    async def _finance_get_upcoming(self, days_ahead: int = 30) -> str:
        content = self.memory.read("finances")
        if not content:
            return "No finance data found"
        today = now_ksa()
        current_day = today.day
        lines = []
        for line in content.split("\n"):
            due_match = re.search(r"Due:\s*(\d+)(?:th|st|nd|rd)?", line)
            if due_match:
                due_day = int(due_match.group(1))
                days_until_due = due_day - current_day
                if days_until_due < 0:
                    days_until_due += 30
                if days_until_due <= days_ahead:
                    urgency = "🔴" if days_until_due <= 3 else "🟡" if days_until_due <= 7 else "🟢"
                    lines.append(f"{urgency} {line.strip()} ({days_until_due}d)")
        return "\n".join(lines) if lines else "No upcoming bills in the next {days_ahead} days"

    async def _finance_add_subscription(self, service: str, amount: str, renews_day: str) -> str:
        entry = f"- [{service}] {amount}/month - Renews: {renews_day}"
        self.memory.append_to_section("finances", "Subscriptions", entry)
        return f"Subscription tracked: {service} ({amount}/month)"

    async def _health_add_medication(self, name: str, dosage: str = "", frequency: str = "") -> str:
        entry = f"- {name}: {dosage}, {frequency}"
        self.memory.append_to_section("health", "Medications", entry)
        return f"Medication tracked: {name}"

    async def _health_log_vitals(
        self, weight: Optional[str] = None, bp: Optional[str] = None, notes: Optional[str] = None
    ) -> str:
        parts = [f"[{ksa_today_str()}]"]
        if weight:
            parts.append(f"Weight: {weight}kg")
        if bp:
            parts.append(f"BP: {bp}")
        if notes:
            parts.append(notes)
        self.memory.append_to_section("health", "Vitals Log", " ".join(parts))
        return "Vitals logged"

    async def _health_add_doctor(self, name: str, specialty: str, phone: str = "", next_visit: str = "") -> str:
        entry = f"- Dr. {name} ({specialty}) - {phone}"
        if next_visit:
            entry += f" - Next visit: {next_visit}"
        self.memory.append_to_section("health", "Doctors", entry)
        return f"Doctor added: Dr. {name}"

    async def _home_add_maintenance(self, issue: str, resolution: str = "", date: Optional[str] = None) -> str:
        entry_date = date or ksa_today_str()
        entry = f"- [{entry_date}] {issue}"
        if resolution:
            entry += f" - {resolution}"
        self.memory.append_to_section("home", "Maintenance Log", entry)
        return f"Maintenance logged: {issue}"

    async def _home_get_warranties(self) -> str:
        content = self.memory.read("home")
        if not content:
            return "No home data found"
        warranties = []
        for line in content.split("\n"):
            if "arranty" in line.lower() or "xpire" in line.lower():
                warranties.append(line.strip())
        return "\n".join(warranties) if warranties else "No warranties tracked"

    async def _home_add_appliance(self, name: str, brand: str, warranty_expires: str = "") -> str:
        entry = f"- [{name}] {brand}"
        if warranty_expires:
            entry += f" - Warranty expires: {warranty_expires}"
        self.memory.append_to_section("home", "Appliances & Warranties", entry)
        return f"Appliance tracked: {name}"

    async def _document_add(self, name: str, number: str, expires: str = "", location: str = "") -> str:
        entry = f"- {name}: {number}"
        if expires:
            entry += f" - Expires: {expires}"
        if location:
            entry += f" - Location: {location}"
        self.memory.append_to_section("documents", "Other Documents", entry)
        return f"Document tracked: {name}"

    async def _document_get_expiring(self, days_ahead: int = 90) -> str:
        items = self.memory.get_expiring_items(days_ahead)
        doc_items = [i for i in items if i["category"] == "documents"]
        if not doc_items:
            return "No documents expiring soon"
        return "\n".join(f"- [{i['days_left']}d] {i['detail']}" for i in doc_items)

    async def _learning_add_course(self, name: str, platform: str = "", progress: str = "0%") -> str:
        entry = f"- {name} - {platform} - Progress: {progress}"
        self.memory.append_to_section("learning", "Current Courses", entry)
        return f"Course tracked: {name}"

    async def _learning_update_progress(self, course_name: str, progress: str) -> str:
        content = self.memory.read("learning")
        if not content:
            return "No learning data found"
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if course_name.lower() in line.lower():
                lines[i] = re.sub(r"Progress: \d+%", f"Progress: {progress}", line)
                self.memory.write("learning", "\n".join(lines))
                return f"Progress updated: {course_name} is now {progress}"
        return f"Course not found: {course_name}"

    async def _get_expiring_items(self, days: int = 90) -> str:
        items = self.memory.get_expiring_items(days)
        if not items:
            return "Nothing expiring soon"
        return "\n".join(f"- [{i['days_left']}d] [{i['category']}] {i['detail']}" for i in items)
