"""Microsoft Graph MCP Server - integrates with Outlook email and MS Calendar."""

from datetime import timedelta

from moha_mind.agent.memory import MemoryManager
from moha_mind.config import settings
from moha_mind.utils.logging_config import log
from moha_mind.utils.timezone import now_ksa


class MicrosoftGraphServer:
    def __init__(self, memory: MemoryManager):
        self.memory = memory
        self._client = None

    def _get_client(self):
        if self._client:
            return self._client
        try:
            from azure.identity import ClientSecretCredential, DeviceCodeCredential
            from msgraph import GraphServiceClient

            tenant_id = settings.ms_tenant_id
            client_id = settings.ms_client_id
            client_secret = settings.ms_client_secret

            if not client_id or not client_secret:
                log.warning("Microsoft Graph credentials not configured. MS integration disabled.")
                return None

            if client_secret and tenant_id != "common":
                credential = ClientSecretCredential(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret,
                )
            else:
                credential = DeviceCodeCredential(
                    client_id=client_id,
                    tenant_id=tenant_id,
                )

            self._client = GraphServiceClient(credential)
            return self._client
        except Exception as e:
            log.error(f"Microsoft Graph auth failed: {e}")
            return None

    async def handle_tool(self, tool_name: str, arguments: dict) -> str:
        handlers = {
            "ms_list_emails": self._list_emails,
            "ms_list_calendar_events": self._list_calendar_events,
            "ms_create_calendar_event": self._create_calendar_event,
            "ms_send_email": self._send_email,
            "get_ms_calendar_events": self._list_calendar_events,
        }
        handler = handlers.get(tool_name)
        if handler:
            return await handler(**arguments)
        return f"Unknown tool: {tool_name}"

    async def _list_emails(self, count: int = 5, folder: str = "inbox") -> str:
        client = self._get_client()
        if not client:
            return "Microsoft Graph not configured"

        try:
            messages = await client.me.messages.get(
                request_configuration=lambda c: (
                    setattr(c.query_parameters, "top", count)
                    or setattr(c.query_parameters, "orderby", ["receivedDateTime desc"])
                )
            )

            if not messages.value:
                return "No emails found"

            lines = []
            for msg in messages.value:
                sender = msg.sender.email_address.name if msg.sender else "Unknown"
                subject = msg.subject or "No subject"
                received = msg.received_date_time.strftime("%Y-%m-%d %H:%M") if msg.received_date_time else ""
                lines.append(f"- [{received}] From: {sender} - {subject}")

            return "\n".join(lines)
        except Exception as e:
            log.error(f"MS Graph list emails failed: {e}")
            return f"Error fetching emails: {e}"

    async def _list_calendar_events(self, days_ahead: int = 1) -> str:
        client = self._get_client()
        if not client:
            return "Microsoft Graph not configured"

        try:
            now = now_ksa().replace(hour=0, minute=0, second=0, microsecond=0)
            end = now + timedelta(days=days_ahead)

            from kiota_abstractions.base_request_configuration import RequestConfiguration
            from msgraph.users.item.calendar_view.calendar_view_request_builder import CalendarViewRequestBuilder

            query_params = CalendarViewRequestBuilder.CalendarViewRequestBuilderGetQueryParameters(
                start_date_time=now.isoformat(),
                end_date_time=end.isoformat(),
                orderby=["start/dateTime"],
            )
            config = RequestConfiguration(query_parameters=query_params)

            events = await client.me.calendar_view.get(config)

            if not events.value:
                return f"No Outlook calendar events for the next {days_ahead} day(s)"

            lines = []
            for event in events.value:
                start = event.start.date_time if event.start else "Unknown time"
                subject = event.subject or "No title"
                location = event.location.display_name if event.location else ""
                loc_str = f" @ {location}" if location else ""
                lines.append(f"- {start[:16]} {subject}{loc_str}")

            return "\n".join(lines)
        except Exception as e:
            log.error(f"MS Graph list events failed: {e}")
            return f"Error fetching calendar: {e}"

    async def _create_calendar_event(
        self, subject: str, start_time: str, end_time: str, body: str = "", location: str = ""
    ) -> str:
        client = self._get_client()
        if not client:
            return "Microsoft Graph not configured"

        try:
            from msgraph.generated.models.date_time_time_zone import DateTimeTimeZone
            from msgraph.generated.models.event import Event
            from msgraph.generated.models.item_body import ItemBody
            from msgraph.generated.models.location import Location

            event = Event()
            event.subject = subject
            event.body = ItemBody(content=body)
            event.start = DateTimeTimeZone(date_time=start_time, time_zone="Asia/Riyadh")
            event.end = DateTimeTimeZone(date_time=end_time, time_zone="Asia/Riyadh")
            if location:
                event.location = Location(display_name=location)

            await client.me.events.post(event)
            return f"Outlook event created: {subject}"
        except Exception as e:
            log.error(f"MS Graph create event failed: {e}")
            return f"Error creating event: {e}"

    async def _send_email(self, to: str, subject: str, body: str) -> str:
        client = self._get_client()
        if not client:
            return "Microsoft Graph not configured"

        try:
            from msgraph.generated.models.email_address import EmailAddress
            from msgraph.generated.models.item_body import ItemBody
            from msgraph.generated.models.message import Message
            from msgraph.generated.models.recipient import Recipient

            message = Message()
            message.subject = subject
            message.body = ItemBody(content=body)
            message.to_recipients = [Recipient(email_address=EmailAddress(address=to))]

            await client.me.send_mail.post(body={"message": message})
            return f"Email sent to {to}: {subject}"
        except Exception as e:
            log.error(f"MS Graph send email failed: {e}")
            return f"Error sending email: {e}"
