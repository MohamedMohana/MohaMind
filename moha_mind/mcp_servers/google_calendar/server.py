"""Google Calendar MCP Server - integrates with Google Calendar API."""

import os
from datetime import datetime, timedelta

from moha_mind.agent.memory import MemoryManager
from moha_mind.config import settings
from moha_mind.utils.logging_config import log
from moha_mind.utils.timezone import KSA_TZ, now_ksa


class GoogleCalendarServer:
    def __init__(self, memory: MemoryManager):
        self.memory = memory
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build

            creds = None
            token_path = settings.google_token_path
            cred_path = settings.google_credentials_path

            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(
                    token_path,
                    [
                        "https://www.googleapis.com/auth/calendar.readonly",
                        "https://www.googleapis.com/auth/calendar.events",
                    ],
                )

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                elif os.path.exists(cred_path):
                    flow = InstalledAppFlow.from_client_secrets_file(
                        cred_path,
                        [
                            "https://www.googleapis.com/auth/calendar.readonly",
                            "https://www.googleapis.com/auth/calendar.events",
                        ],
                    )
                    creds = flow.run_local_server(port=0)
                else:
                    log.warning("Google credentials not found. Calendar integration disabled.")
                    return None

            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            with open(token_path, "w") as token:
                token.write(creds.to_json())

            self._service = build("calendar", "v3", credentials=creds)
            return self._service
        except Exception as e:
            log.error(f"Google Calendar auth failed: {e}")
            return None

    async def handle_tool(self, tool_name: str, arguments: dict) -> str:
        handlers = {
            "google_list_events": self._list_events,
            "google_create_event": self._create_event,
            "google_find_free_time": self._find_free_time,
            "get_calendar_events": self._list_events,
        }
        handler = handlers.get(tool_name)
        if handler:
            return await handler(**arguments)
        return f"Unknown tool: {tool_name}"

    async def _list_events(self, days_ahead: int = 1, calendar_id: str = "primary") -> str:
        service = self._get_service()
        if not service:
            return "Google Calendar not configured. Run setup first."

        try:
            now = now_ksa().replace(hour=0, minute=0, second=0, microsecond=0)
            end = now + timedelta(days=days_ahead)

            events_result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=now.isoformat() + "+03:00",
                    timeMax=end.isoformat() + "+03:00",
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            if not events:
                return f"No Google Calendar events for the next {days_ahead} day(s)"

            lines = []
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date", ""))
                summary = event.get("summary", "No title")
                location = event.get("location", "")
                loc_str = f" @ {location}" if location else ""
                lines.append(f"- {start[:16].replace('T', ' ')} {summary}{loc_str}")

            return "\n".join(lines)
        except Exception as e:
            log.error(f"Google Calendar list events failed: {e}")
            return f"Error fetching events: {e}"

    async def _create_event(
        self, summary: str, start_time: str, end_time: str, description: str = "", location: str = ""
    ) -> str:
        service = self._get_service()
        if not service:
            return "Google Calendar not configured"

        try:
            event = {
                "summary": summary,
                "location": location,
                "description": description,
                "start": {"dateTime": start_time, "timeZone": "Asia/Riyadh"},
                "end": {"dateTime": end_time, "timeZone": "Asia/Riyadh"},
            }
            created = service.events().insert(calendarId="primary", body=event).execute()
            return f"Event created: {summary} ({created.get('htmlLink', '')})"
        except Exception as e:
            log.error(f"Google Calendar create event failed: {e}")
            return f"Error creating event: {e}"

    async def _find_free_time(self, date: str, duration_minutes: int = 60) -> str:
        service = self._get_service()
        if not service:
            return "Google Calendar not configured"

        try:
            day = datetime.strptime(date, "%Y-%m-%d")
            day_start = day.replace(hour=8, minute=0, tzinfo=KSA_TZ)
            day_end = day.replace(hour=20, minute=0, tzinfo=KSA_TZ)

            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=day_start.isoformat(),
                    timeMax=day_end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            busy_slots = []
            for event in events:
                start = event["start"].get("dateTime", "")
                end = event["end"].get("dateTime", "")
                if start and end:
                    busy_slots.append((start[:16], end[:16]))

            if not busy_slots:
                return f"All clear on {date}! The whole day is free."

            return f"On {date}, you have {len(busy_slots)} events. Suggest checking specific times."
        except Exception as e:
            return f"Error checking free time: {e}"
