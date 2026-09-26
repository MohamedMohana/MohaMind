"""MohaMind Agent Core - The conversation engine.

Handles the main LLM conversation loop with tool calling.
Supports z.ai (Zhipu GLM), OpenAI, and automatic fallback.
All providers use the OpenAI-compatible API format.
"""

import asyncio
import inspect
import json
import re
from typing import Any, Awaitable, Callable, Literal, get_args, get_origin

from openai import AsyncOpenAI

from moha_mind.agent.connected_memory import ConnectedMemory
from moha_mind.agent.embeddings import build_embedder
from moha_mind.agent.energy_tracker import EnergyTracker
from moha_mind.agent.memory import MEMORY_FILES as MEMORY_FILES_KEYS
from moha_mind.agent.memory import MemoryManager
from moha_mind.agent.memory_router import MemoryRouter
from moha_mind.agent.memory_summarizer import MemorySummarizer
from moha_mind.agent.semantic_index import SemanticIndex
from moha_mind.agent.session_store import SessionStore
from moha_mind.agent.system_prompt import build_system_prompt
from moha_mind.agent.verifier import Verifier, VerifierConfig, VerifierVerdict
from moha_mind.config import settings
from moha_mind.utils.arabic_support import (
    build_arabic_understanding_context,
    detect_language,
    normalize_colloquial_arabic,
)
from moha_mind.utils.i18n import t
from moha_mind.utils.logging_config import log


class MohaMindAgent:
    def __init__(self, memory: MemoryManager):
        self.memory = memory
        self.session_store = SessionStore(memory.memory_path)
        self.connected_memory = ConnectedMemory(memory)
        self.energy_tracker = EnergyTracker(memory)

        llm_config = settings.active_llm_config
        self.client = AsyncOpenAI(
            api_key=llm_config["api_key"],
            base_url=llm_config.get("base_url"),
        )
        self.model = llm_config["model"]
        self.provider = llm_config.get("provider", "unknown")

        self.conversations: dict[str, list[dict]] = {}
        self._tool_handlers: dict[str, Callable[..., Awaitable[str]]] = {}
        self._tool_schemas: dict[str, dict] = {}
        # Set by bootstrap when external MCP servers are configured.
        self.external_mcp: Any = None

        self.strategy: str = getattr(settings, "effective_strategy", "fallback")
        self.verifier: Verifier | None = self._build_verifier()

        self.router = MemoryRouter(self.memory, llm_client=self.client, llm_model=self.model)
        self.summarizer = MemorySummarizer(self.memory, llm_client=self.client, llm_model=self.model)

        self.embedder = build_embedder()
        self.semantic_index = SemanticIndex(self.memory, self.embedder)
        if self.embedder:
            log.info(f"Semantic memory enabled: {self.embedder.provider} ({self.embedder.model})")

        log.info(
            f"Agent initialized with {self.provider} (model: {self.model}) | strategy={self.strategy}"
            + (f" | verifier={self.verifier.provider}:{self.verifier.model}" if self.verifier else "")
        )

    def _build_verifier(self) -> Verifier | None:
        if getattr(settings, "effective_strategy", "fallback") != "verify":
            return None
        verifier_cfg = getattr(settings, "verifier_llm_config", None)
        if not verifier_cfg:
            log.warning("LLM strategy is 'verify' but no verifier LLM is configured. Verification disabled.")
            return None
        try:
            return Verifier(
                VerifierConfig(
                    api_key=verifier_cfg["api_key"],
                    model=verifier_cfg["model"],
                    base_url=verifier_cfg.get("base_url"),
                    provider=verifier_cfg.get("provider", "unknown"),
                    strictness=getattr(settings, "verifier_strictness", "balanced"),
                    max_retries=max(1, int(getattr(settings, "verifier_max_retries", 1))),
                )
            )
        except Exception as exc:
            log.warning(f"Failed to build verifier: {exc}")
            return None

    def register_tool(self, name: str, handler: Callable[..., Awaitable[str]], schema: dict | None = None) -> None:
        """Register an external tool handler (from MCP servers).

        `schema` is an optional OpenAI function-calling schema. External MCP
        tools pass theirs through verbatim; without one the schema is inferred
        from the handler signature.
        """
        self._tool_handlers[name] = handler
        if schema is not None:
            self._tool_schemas[name] = schema
        log.info(f"Tool registered: {name}")

    def _annotation_to_schema(self, annotation: Any) -> dict:
        if annotation is inspect.Signature.empty:
            return {"type": "string"}

        origin = get_origin(annotation)
        args = get_args(annotation)

        if origin is Literal:
            return {"type": "string", "enum": list(args)}

        if origin in (list, set, tuple):
            item_schema = self._annotation_to_schema(args[0]) if args else {"type": "string"}
            return {"type": "array", "items": item_schema}

        if origin is dict:
            return {"type": "object"}

        if args and type(None) in args:
            non_null = [arg for arg in args if arg is not type(None)]
            if non_null:
                return self._annotation_to_schema(non_null[0])

        mapping = {
            str: {"type": "string"},
            int: {"type": "integer"},
            float: {"type": "number"},
            bool: {"type": "boolean"},
        }
        return mapping.get(annotation, {"type": "string"})

    def _infer_tool_description(self, name: str, handler: Callable[..., Awaitable[str]]) -> str:
        doc = inspect.getdoc(handler)
        if doc:
            first_line = doc.splitlines()[0].strip()
            if first_line:
                return first_line.rstrip(".")
        return name.replace("_", " ").strip().capitalize()

    def _build_dynamic_tool_schema(self, name: str, handler: Callable[..., Awaitable[str]]) -> dict:
        properties = {}
        required = []

        for param in inspect.signature(handler).parameters.values():
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            properties[param.name] = self._annotation_to_schema(param.annotation)
            if param.default is inspect.Signature.empty:
                required.append(param.name)

        parameters = {
            "type": "object",
            "properties": properties,
        }
        if required:
            parameters["required"] = required

        return {
            "type": "function",
            "function": {
                "name": name,
                "description": self._infer_tool_description(name, handler),
                "parameters": parameters,
            },
        }

    def _base_tools_schema(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "save_memory",
                    "description": (
                        "Append new information to a memory category without deleting existing memory. "
                        "Categories: profile, family, tasks, occasions, vehicle, finances, "
                        "health, home, documents, travel, learning, shopping, relationships, energy_log"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Memory category to save to",
                            },
                            "content": {
                                "type": "string",
                                "description": "Content to save",
                            },
                        },
                        "required": ["category", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_memory",
                    "description": "Search across all memory files for information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query",
                            },
                            "categories": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional: specific categories to search",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "semantic_search_memory",
                    "description": (
                        "Semantic search across memory (finds conceptually related lines, not just exact words). "
                        "Use when the user asks vague or paraphrased questions."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Natural-language search query"},
                            "top_k": {"type": "integer", "description": "Max results (default 5)"},
                            "categories": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional: restrict to these categories",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_sessions",
                    "description": "Search past conversation history for relevant details",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for past conversations",
                            },
                            "chat_id": {
                                "type": "string",
                                "description": "Optional: limit the search to a specific chat or platform thread",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_task",
                    "description": "Add a new task to the task list",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Task description",
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "Task priority",
                            },
                            "due": {
                                "type": "string",
                                "description": "Due date in YYYY-MM-DD format",
                            },
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "complete_task",
                    "description": "Mark a task as completed",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_text": {
                                "type": "string",
                                "description": "Description of the task to complete",
                            },
                        },
                        "required": ["task_text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_tasks",
                    "description": "List all active (incomplete) tasks",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_expiring",
                    "description": (
                        "Get items expiring within a given number of days (documents, insurance, subscriptions, etc.)"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "Number of days to look ahead (default 90)",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_calendar_events",
                    "description": "Get calendar events from Google Calendar",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days_ahead": {
                                "type": "integer",
                                "description": "Number of days ahead to check (default 1 for today)",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "append_to_section",
                    "description": "Append a line to a specific section in a memory file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Memory category",
                            },
                            "section": {
                                "type": "string",
                                "description": "Section header (without ##)",
                            },
                            "line": {
                                "type": "string",
                                "description": "Line to append",
                            },
                        },
                        "required": ["category", "section", "line"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_note",
                    "description": "Save a quick note to the notes folder",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Note title",
                            },
                            "content": {
                                "type": "string",
                                "description": "Note content",
                            },
                        },
                        "required": ["title", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_daily_log",
                    "description": "Save a daily log entry summarizing conversations or activities",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "Summary text to log",
                            },
                        },
                        "required": ["summary"],
                    },
                },
            },
        ]

    def get_tools_schema(self) -> list[dict]:
        """Get the JSON schema for all available tools (OpenAI function calling format)."""
        schemas = self._base_tools_schema()
        known_names = {schema["function"]["name"] for schema in schemas}

        for name, handler in self._tool_handlers.items():
            if name in known_names:
                continue
            explicit = self._tool_schemas.get(name)
            schemas.append(explicit if explicit is not None else self._build_dynamic_tool_schema(name, handler))

        return schemas

    async def _execute_model_tool_call(self, tool_call: Any) -> str:
        tool_name = tool_call.function.name
        log.info("Tool call: %s", tool_name)
        try:
            arguments = json.loads(tool_call.function.arguments)
        except (json.JSONDecodeError, TypeError):
            return "Error: tool arguments must be valid JSON. The tool was not executed."
        if not isinstance(arguments, dict):
            return "Error: tool arguments must be a JSON object. The tool was not executed."

        try:
            result = await asyncio.wait_for(
                self.handle_tool_call(tool_name, arguments),
                timeout=settings.agent_tool_timeout_seconds,
            )
        except TimeoutError:
            log.warning("Tool timed out: %s", tool_name)
            result = (
                "Error: tool timed out; outcome is unknown. It may have completed externally. "
                "Check state before retrying a change."
            )

        result = str(result)
        limit = settings.agent_max_tool_result_chars
        if len(result) > limit:
            suffix = "\n[Tool result truncated; request a narrower query for more detail.]"
            result = result[: limit - len(suffix)] + suffix
        return result

    async def _execute_tool_batch(self, tool_calls: list[Any], remaining_calls: int) -> list[dict]:
        messages = []
        for index, tool_call in enumerate(tool_calls):
            if index >= remaining_calls:
                result = "Error: tool-call limit reached. This tool was not executed."
            else:
                result = await self._execute_model_tool_call(tool_call)
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
        return messages

    async def handle_tool_call(self, tool_name: str, arguments: dict) -> str:
        """Handle a tool call from the LLM."""
        if tool_name in self._tool_handlers:
            try:
                return await self._tool_handlers[tool_name](**arguments)
            except Exception as e:
                log.error(f"External tool '{tool_name}' failed: {e}")
                return f"Error calling {tool_name}: {str(e)}"

        try:
            match tool_name:
                case "save_memory":
                    self.memory.save_entry(arguments["category"], arguments["content"])
                    connections = self.connected_memory.process_new_info(arguments["content"])
                    extra = ""
                    if connections:
                        extra = " | Connected: " + "; ".join(connections)
                    return f"Saved to {arguments['category']}{extra}"

                case "search_memory":
                    return self._hybrid_search_memory(
                        arguments["query"],
                        arguments.get("categories"),
                    )

                case "semantic_search_memory":
                    if not self.semantic_index.is_available():
                        return "Semantic search is not enabled. (Set EMBEDDING_BACKEND to 'openai' or 'local'.)"
                    try:
                        self.semantic_index.sync()
                    except Exception as exc:
                        log.debug(f"Semantic sync during search failed: {exc}")
                    semantic = self.semantic_index.search(
                        arguments["query"],
                        top_k=int(arguments.get("top_k") or settings.semantic_top_k or 5),
                        categories=arguments.get("categories"),
                    )
                    if not semantic:
                        return "No semantic matches."
                    lines = []
                    for r in semantic:
                        lines.append(f"[{r.category}:{r.line_number} · {r.score:.2f}] {r.chunk}")
                    return "\n".join(lines)

                case "search_sessions":
                    results = self.session_store.search_messages(
                        query=arguments["query"],
                        chat_id=arguments.get("chat_id"),
                        limit=arguments.get("limit", 5),
                    )
                    if not results:
                        return "No past conversation matches found"
                    return self._format_session_results(results)

                case "add_task":
                    self.memory.add_task(
                        text=arguments["text"],
                        priority=arguments.get("priority", "medium"),
                        due=arguments.get("due"),
                    )
                    connections = self.connected_memory.process_new_info(arguments["text"])
                    return f"Task added: {arguments['text']}"

                case "complete_task":
                    success = self.memory.complete_task(arguments["task_text"])
                    return "Task completed!" if success else "Task not found"

                case "list_tasks":
                    tasks = self.memory.get_task_section()
                    active = [t for t in tasks if not t["done"]]
                    if not active:
                        return "No active tasks"
                    return "\n".join(
                        f"- [{t['priority'].upper()}] {t['text']}" + (f" (due {t['due']})" if t["due"] else "")
                        for t in active
                    )

                case "get_expiring":
                    items = self.memory.get_expiring_items(arguments.get("days", 90))
                    if not items:
                        return "Nothing expiring soon"
                    return "\n".join(f"- [{i['days_left']}d] {i['detail']}" for i in items)

                case "append_to_section":
                    self.memory.append_to_section(
                        arguments["category"],
                        arguments["section"],
                        arguments["line"],
                    )
                    return f"Added to {arguments['category']} > {arguments['section']}"

                case "save_note":
                    path = self.memory.save_note(arguments["title"], arguments["content"])
                    return f"Note saved: {path.name}"

                case "save_daily_log":
                    self.memory.save_daily_log(arguments["summary"])
                    return "Daily log updated"

                case _:
                    return f"Unknown tool: {tool_name}"

        except Exception as e:
            log.error(f"Tool '{tool_name}' execution failed: {e}")
            return f"Error: {str(e)}"

    def _hybrid_search_memory(self, query: str, categories: list[str] | None) -> str:
        """FTS/substring results first, semantic results merged in below."""
        lexical = self.memory.search(query, categories)
        lexical_chunks = [f"[{r['category']}:{r['line_number']}] {r['context']}" for r in lexical[:10]]

        semantic_chunks: list[str] = []
        if self.semantic_index.is_available():
            try:
                self.semantic_index.sync()
                semantic = self.semantic_index.search(
                    query,
                    top_k=int(getattr(settings, "semantic_top_k", 5) or 5),
                    categories=categories,
                )
                lexical_lines = {(r["category"], r["line_number"]) for r in lexical}
                for r in semantic:
                    if (r.category, r.line_number) in lexical_lines:
                        continue
                    semantic_chunks.append(f"[{r.category}:{r.line_number} · sim={r.score:.2f}] {r.chunk}")
            except Exception as exc:
                log.debug(f"Semantic search branch failed: {exc}")

        out: list[str] = []
        if lexical_chunks:
            out.append("Exact matches:")
            out.extend(lexical_chunks)
        if semantic_chunks:
            if out:
                out.append("")
            out.append("Related (semantic):")
            out.extend(semantic_chunks)
        if not out:
            return "No results found"
        return "\n".join(out)

    def _truncate_text(self, text: str, limit: int = 180) -> str:
        clean = " ".join(text.split())
        if len(clean) <= limit:
            return clean
        return clean[: limit - 3].rstrip() + "..."

    def _format_session_results(self, results: list[dict]) -> str:
        lines = []
        for result in results:
            when = result.get("created_at", "").replace("T", " ")
            lines.append(f"[{result['chat_id']} | {result['role']} | {when}] {self._truncate_text(result['content'])}")
        return "\n".join(lines)

    def _route_memory_context(self, message: str) -> tuple[list[str] | None, dict[str, str] | None]:
        """Pick focus categories + summaries for the system prompt.

        Returns (None, None) when the memory router is disabled — in that case
        the prompt falls back to the legacy full-dump behavior.
        """
        if not getattr(settings, "memory_router_enabled", True):
            return None, None

        max_cats = max(1, int(getattr(settings, "memory_router_max_categories", 4)))
        try:
            decision = self.router.pick(message, max_categories=max_cats)
            focus = decision.categories
        except Exception as exc:
            log.debug(f"Memory router failed, falling back to defaults: {exc}")
            focus = ["profile", "tasks", "reminders"]

        summaries: dict[str, str] | None = None
        if getattr(settings, "memory_summaries_enabled", True):
            try:
                summaries = self.summarizer.get_summaries(list(MEMORY_FILES_KEYS))
            except Exception as exc:
                log.debug(f"Summary fetch failed: {exc}")
                summaries = None
        return focus, summaries

    def _build_recall_context(self, message: str, chat_id: str) -> str:
        normalized_message, _ = normalize_colloquial_arabic(message)
        recall_query = normalized_message if normalized_message else message
        tokens = [token for token in re.findall(r"\w+", recall_query, flags=re.UNICODE) if len(token) >= 3]
        if not tokens:
            return ""

        results = self.session_store.search_messages(recall_query, chat_id=chat_id, limit=3)
        if not results:
            return ""

        lines = [
            "### RELEVANT PAST CONVERSATION",
            "Use this only when it materially helps answer the current request.",
        ]
        for result in results:
            when = result.get("created_at", "").replace("T", " ")
            lines.append(f"- [{when}] {result['role']}: {self._truncate_text(result['content'], 140)}")
        return "\n".join(lines)

    def recall(self, query: str, chat_id: str = "default", limit: int = 5, language: str = "en") -> str:
        memory_results = self.memory.search(query)[:limit]
        session_results = self.session_store.search_messages(query, chat_id=chat_id, limit=limit)

        if not memory_results and not session_results:
            if language == "ar":
                return f"لا توجد نتائج عن «{query}» في الذاكرة أو المحادثات السابقة."
            return f"No results found for '{query}' in memory or past conversations."

        lines = []

        if memory_results:
            lines.append("### الذاكرة المنظمة" if language == "ar" else "### Structured Memory")
            for result in memory_results:
                snippet = self._truncate_text(result["matched_line"], 120)
                lines.append(f"- [{result['category']}:{result['line_number']}] {snippet}")

        if session_results:
            if lines:
                lines.append("")
            lines.append("### المحادثات السابقة" if language == "ar" else "### Past Conversations")
            for result in session_results:
                when = result.get("created_at", "").replace("T", " ")
                lines.append(f"- [{when}] {result['role']}: {self._truncate_text(result['content'], 120)}")

        return "\n".join(lines)

    def _get_conversation(self, chat_id: str) -> list[dict]:
        """Get or create conversation history for a chat."""
        if chat_id not in self.conversations:
            persisted = self.session_store.load_recent_messages(chat_id, limit=20)
            self.conversations[chat_id] = [{"role": item["role"], "content": item["content"]} for item in persisted]
        return self.conversations[chat_id]

    def _normalize_tool_call(self, tool_call: Any) -> dict | None:
        if isinstance(tool_call, dict):
            call_id = tool_call.get("id")
            call_type = tool_call.get("type") or "function"
            function = tool_call.get("function") or {}
        else:
            call_id = getattr(tool_call, "id", None)
            call_type = getattr(tool_call, "type", "function") or "function"
            function = getattr(tool_call, "function", None) or {}

        if isinstance(function, dict):
            name = function.get("name")
            arguments = function.get("arguments") or "{}"
        else:
            name = getattr(function, "name", None)
            arguments = getattr(function, "arguments", "{}") or "{}"

        if not call_id or not name:
            return None
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments, ensure_ascii=False)

        return {
            "id": str(call_id),
            "type": str(call_type),
            "function": {
                "name": str(name),
                "arguments": arguments,
            },
        }

    def _normalize_conversation_message(self, message: dict) -> dict | None:
        role = message.get("role")

        if role in ("user", "system"):
            content = message.get("content")
            if content is None:
                return None
            return {"role": role, "content": str(content)}

        if role == "assistant":
            tool_calls = [
                normalized
                for tool_call in (message.get("tool_calls") or [])
                if (normalized := self._normalize_tool_call(tool_call)) is not None
            ]
            content = message.get("content")
            if tool_calls:
                return {"role": "assistant", "content": content, "tool_calls": tool_calls}
            if content is None:
                return None
            return {"role": "assistant", "content": str(content)}

        if role == "tool":
            tool_call_id = message.get("tool_call_id")
            if not tool_call_id:
                return None
            return {
                "role": "tool",
                "tool_call_id": str(tool_call_id),
                "content": str(message.get("content") or ""),
            }

        return None

    def _valid_conversation_units(self, conversation: list[dict]) -> list[list[dict]]:
        normalized = [
            message
            for raw_message in conversation
            if (message := self._normalize_conversation_message(raw_message)) is not None
        ]
        units: list[list[dict]] = []
        index = 0

        while index < len(normalized):
            message = normalized[index]
            if message["role"] == "assistant" and message.get("tool_calls"):
                expected_ids = [tool_call["id"] for tool_call in message["tool_calls"]]
                seen_ids: set[str] = set()
                group = [message]
                index += 1

                while index < len(normalized) and normalized[index]["role"] == "tool":
                    tool_message = normalized[index]
                    tool_call_id = tool_message["tool_call_id"]
                    if tool_call_id in expected_ids and tool_call_id not in seen_ids:
                        group.append(tool_message)
                        seen_ids.add(tool_call_id)
                    index += 1

                if len(seen_ids) == len(expected_ids):
                    units.append(group)
                continue

            if message["role"] != "tool":
                units.append([message])
            index += 1

        return units

    def _trim_conversation_for_llm(self, conversation: list[dict], max_messages: int = 20) -> list[dict]:
        turns: list[list[dict]] = []
        current_turn: list[dict] = []

        for unit in self._valid_conversation_units(conversation):
            if unit[0]["role"] == "user":
                if current_turn:
                    turns.append(current_turn)
                current_turn = [*unit]
            else:
                current_turn.extend(unit)

        if current_turn:
            turns.append(current_turn)

        selected: list[list[dict]] = []
        selected_count = 0
        for turn in reversed(turns):
            turn_size = len(turn)
            if selected and selected_count + turn_size > max_messages:
                break
            selected.append(turn)
            selected_count += turn_size

        trimmed: list[dict] = []
        for turn in reversed(selected):
            trimmed.extend(turn)
        return trimmed

    def _build_llm_messages(self, system_prompt: str, conversation: list[dict], max_messages: int = 20) -> list[dict]:
        return [
            {"role": "system", "content": system_prompt},
            *self._trim_conversation_for_llm(conversation, max_messages=max_messages),
        ]

    def _switch_to_fallback(self) -> bool:
        """Switch to fallback LLM if available. Returns True if switched."""
        fallback = settings.fallback_llm_config
        if not fallback:
            return False
        if fallback.get("provider") == self.provider and fallback.get("model") == self.model:
            return False
        self.client = AsyncOpenAI(
            api_key=fallback["api_key"],
            base_url=fallback.get("base_url"),
        )
        self.model = fallback["model"]
        self.provider = fallback.get("provider", "fallback")
        log.info(f"Switched to fallback LLM: {self.provider} ({self.model})")
        return True

    async def _chat_completion_with_fallback(self, **kwargs):
        try:
            return await self.client.chat.completions.create(model=self.model, **kwargs)
        except Exception as e:
            log.error(f"{self.provider} API error: {e}")
            if not self._switch_to_fallback():
                raise
            try:
                return await self.client.chat.completions.create(model=self.model, **kwargs)
            except Exception as e2:
                log.error(f"Fallback ({self.provider}) also failed: {e2}")
                raise

    async def chat(self, message: str, chat_id: str = "default") -> str:
        """Main conversation method. Process a user message and return a response."""
        conversation = self._get_conversation(chat_id)
        recall_context = self._build_recall_context(message, chat_id)
        arabic_context = build_arabic_understanding_context(message)
        extra_parts = [part for part in (arabic_context, recall_context) if part]

        focus, summaries = self._route_memory_context(message)
        system_prompt = build_system_prompt(
            self.memory,
            extra_context="\n\n".join(extra_parts),
            focus_categories=focus,
            summaries=summaries,
        )

        # Tag memory writes made during this turn as user-initiated.
        self.memory.set_write_source("user")

        conversation.append({"role": "user", "content": message})
        self.session_store.append_message(chat_id, "user", message)

        max_tool_rounds = settings.agent_max_tool_rounds
        remaining_calls = settings.agent_max_tool_calls
        final_response = ""

        for round_num in range(max_tool_rounds):
            try:
                response = await self._chat_completion_with_fallback(
                    messages=self._build_llm_messages(system_prompt, conversation),
                    tools=self.get_tools_schema(),
                    tool_choice="auto",
                    max_tokens=1500,
                    temperature=0.7,
                )
            except Exception as e:
                log.error(f"Chat generation failed: {e}")
                return "I'm having trouble connecting right now. Please try again in a moment."

            choice = response.choices[0]
            assistant_message = choice.message

            if assistant_message.tool_calls:
                conversation.append(assistant_message.model_dump())

                conversation.extend(await self._execute_tool_batch(assistant_message.tool_calls, remaining_calls))
                remaining_calls -= len(assistant_message.tool_calls)
                if remaining_calls <= 0:
                    break
            else:
                final_response = assistant_message.content or ""
                conversation.append({"role": "assistant", "content": final_response})
                break

        if not final_response:
            # Tool budget exhausted without a user-facing reply. Force one by
            # disabling tools so the model must summarize what it already did.
            log.warning("No final reply after %s rounds; forcing final reply without tools.", round_num + 1)
            try:
                forced_messages = self._build_llm_messages(system_prompt, conversation)
                forced_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Summarize the result of my previous request for me now, in the same language "
                            "I used. Do not call any more tools."
                        ),
                    }
                )
                forced = await self._chat_completion_with_fallback(
                    messages=forced_messages,
                    max_tokens=800,
                    temperature=0.5,
                )
                final_response = (forced.choices[0].message.content or "").strip()
            except Exception as exc:
                log.error(f"Forced final reply failed: {exc}")

        if not final_response:
            final_response = t("chat.done_fallback", lang=detect_language(message))
            conversation.append({"role": "assistant", "content": final_response})
        elif not conversation or conversation[-1].get("role") != "assistant":
            conversation.append({"role": "assistant", "content": final_response})

        final_response = await self._maybe_verify_and_revise(
            message=message,
            current_reply=final_response,
            conversation=conversation,
            system_prompt=system_prompt,
        )

        if len(conversation) > 50:
            self.conversations[chat_id] = self._trim_conversation_for_llm(conversation, max_messages=30)

        self.session_store.append_message(chat_id, "assistant", final_response)
        self.energy_tracker.log_interaction(message, len(final_response))
        return final_response

    async def _maybe_verify_and_revise(
        self,
        *,
        message: str,
        current_reply: str,
        conversation: list[dict],
        system_prompt: str,
    ) -> str:
        """If the verifier strategy is enabled, ask it to check the reply and optionally retry."""
        if not self.verifier or not current_reply.strip():
            return current_reply

        language = detect_language(message)
        max_retries = max(1, self.verifier.config.max_retries)
        reply = current_reply

        for attempt in range(max_retries):
            try:
                verdict: VerifierVerdict = await self.verifier.review(message, reply, language_hint=language)
            except Exception as exc:
                log.warning(f"Verifier review crashed: {exc}")
                return reply

            if verdict.ok or verdict.severity in ("none", "low"):
                if verdict.issues:
                    log.info(
                        f"Verifier accepted reply (severity={verdict.severity}) with minor notes: {verdict.issues}"
                    )
                return reply

            log.info(
                f"Verifier flagged reply (severity={verdict.severity}, attempt={attempt + 1}/{max_retries}): "
                f"{verdict.issues} | suggestion: {verdict.suggestion}"
            )

            revise_prompt = (
                "A second reviewer (the verifier) checked your previous answer and found issues.\n"
                f"Issues: {'; '.join(verdict.issues) or 'unspecified'}\n"
                f"Reviewer suggestion: {verdict.suggestion or 'revise the reply'}\n\n"
                "Rewrite your previous answer to address these issues. Keep the same language as the user. "
                "Do not apologize or mention the reviewer — just produce a better answer."
            )

            try:
                revision_messages = self._build_llm_messages(system_prompt, conversation)
                revision_messages.append({"role": "user", "content": revise_prompt})
                response = await self._chat_completion_with_fallback(
                    messages=revision_messages,
                    max_tokens=1500,
                    temperature=0.5,
                )
            except Exception as exc:
                log.warning(f"Verifier-driven revision failed: {exc}")
                return reply

            new_reply = (response.choices[0].message.content or "").strip()
            if not new_reply:
                return reply

            # Replace the last assistant turn in the conversation with the revised one.
            for idx in range(len(conversation) - 1, -1, -1):
                if conversation[idx].get("role") == "assistant":
                    conversation[idx] = {"role": "assistant", "content": new_reply}
                    break
            reply = new_reply

        return reply

    async def generate_briefing(self) -> str:
        """Generate the morning briefing with one bounded batch of tool calls."""
        system_prompt = build_system_prompt(self.memory, extra_context=t("briefing.mode"))
        briefing_request = t("briefing.prompt")

        try:
            response = await self._chat_completion_with_fallback(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": briefing_request},
                ],
                tools=self.get_tools_schema(),
                tool_choice="auto",
                max_tokens=2000,
                temperature=0.7,
            )

            choice = response.choices[0]
            if choice.message.tool_calls:
                conversation = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": briefing_request},
                    choice.message.model_dump(),
                ]
                conversation.extend(
                    await self._execute_tool_batch(choice.message.tool_calls, settings.agent_max_tool_calls)
                )

                response = await self._chat_completion_with_fallback(
                    messages=conversation,
                    max_tokens=2000,
                    temperature=0.7,
                )
                return response.choices[0].message.content or ""

            return choice.message.content or ""

        except Exception as e:
            log.error(f"Briefing generation failed: {e}")
            return t("briefing.generation_error", error=e)

    async def generate_weekly_review(self) -> str:
        """Generate the weekly life review."""
        system_prompt = build_system_prompt(self.memory, extra_context=t("review.mode"))
        review_request = t("review.prompt")

        try:
            response = await self._chat_completion_with_fallback(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": review_request},
                ],
                tools=self.get_tools_schema(),
                tool_choice="auto",
                max_tokens=2500,
                temperature=0.7,
            )

            choice = response.choices[0]
            if choice.message.tool_calls:
                conversation = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": review_request},
                    choice.message.model_dump(),
                ]
                conversation.extend(
                    await self._execute_tool_batch(choice.message.tool_calls, settings.agent_max_tool_calls)
                )

                response = await self._chat_completion_with_fallback(
                    messages=conversation,
                    max_tokens=2500,
                    temperature=0.7,
                )
                return response.choices[0].message.content or ""

            return choice.message.content or ""
        except Exception as e:
            log.error(f"Weekly review generation failed: {e}")
            return t("review.error")
