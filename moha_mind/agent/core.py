"""MohaMind Agent Core - The conversation engine.

Handles the main LLM conversation loop with tool calling.
Supports z.ai (Zhipu GLM), OpenAI, and automatic fallback.
All providers use the OpenAI-compatible API format.
"""

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

    def register_tool(self, name: str, handler: Callable[..., Awaitable[str]]) -> None:
        """Register an external tool handler (from MCP servers)."""
        self._tool_handlers[name] = handler
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
                        "Save information to a memory category. "
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
            schemas.append(self._build_dynamic_tool_schema(name, handler))

        return schemas

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
                    self.memory.write(arguments["category"], arguments["content"])
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
            lines.append(
                f"[{result['chat_id']} | {result['role']} | {when}] {self._truncate_text(result['content'])}"
            )
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

        max_tool_rounds = 10
        final_response = ""

        for round_num in range(max_tool_rounds):
            try:
                response = await self._chat_completion_with_fallback(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *conversation[-20:],
                    ],
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

                for tool_call in assistant_message.tool_calls:
                    func_name = tool_call.function.name
                    try:
                        func_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        func_args = {}

                    log.info(f"Tool call: {func_name}({func_args})")
                    tool_result = await self.handle_tool_call(func_name, func_args)

                    conversation.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result,
                        }
                    )
            else:
                final_response = assistant_message.content or ""
                conversation.append({"role": "assistant", "content": final_response})
                break

        if not final_response:
            # Tool budget exhausted without a user-facing reply. Force one by
            # disabling tools so the model must summarize what it already did.
            log.warning(f"Tool-call budget exhausted after {max_tool_rounds} rounds; forcing final reply.")
            try:
                forced = await self._chat_completion_with_fallback(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *conversation[-20:],
                        {
                            "role": "user",
                            "content": (
                                "Summarize the result of my previous request for me now, in the same language "
                                "I used. Do not call any more tools."
                            ),
                        },
                    ],
                    max_tokens=800,
                    temperature=0.5,
                )
                final_response = (forced.choices[0].message.content or "").strip()
            except Exception as exc:
                log.error(f"Forced final reply failed: {exc}")

        if not final_response:
            final_response = "تم تنفيذ طلبك ✅"
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
            self.conversations[chat_id] = conversation[-30:]

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
                response = await self._chat_completion_with_fallback(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *conversation[-20:],
                        {"role": "user", "content": revise_prompt},
                    ],
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
        """Generate the morning briefing without tool calls - just a direct LLM response."""
        system_prompt = build_system_prompt(
            self.memory, extra_context="MODE: Morning Briefing - Generate a comprehensive daily briefing in Arabic"
        )
        briefing_request = (
            "اكتب ملخص الصباح لهذا اليوم باللغة العربية الواضحة والمهنية. "
            "ضمّن مواعيد التقويم، المهام ذات الأولوية، العناصر القريبة من الانتهاء، "
            "اقتراحات مناسبة لليوم، وأي روابط مهمة بين المعلومات. "
            "اجعل النبرة دافئة ومباشرة، واستخدم عناوين قصيرة ونقاطًا مرتبة."
        )

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
                for tool_call in choice.message.tool_calls:
                    func_name = tool_call.function.name
                    try:
                        func_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        func_args = {}
                    tool_result = await self.handle_tool_call(func_name, func_args)
                    conversation.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result,
                        }
                    )

                response = await self._chat_completion_with_fallback(
                    messages=conversation,
                    tools=self.get_tools_schema(),
                    tool_choice="auto",
                    max_tokens=2000,
                    temperature=0.7,
                )
                return response.choices[0].message.content or ""

            return choice.message.content or ""

        except Exception as e:
            log.error(f"Briefing generation failed: {e}")
            return f"صباح الخير. واجهت مشكلة أثناء إعداد ملخصك الكامل اليوم. الخطأ: {e}"

    async def generate_weekly_review(self) -> str:
        """Generate the weekly life review."""
        system_prompt = build_system_prompt(self.memory, extra_context="MODE: Weekly Life Review - Arabic")
        review_request = (
            "اكتب المراجعة الأسبوعية باللغة العربية الواضحة والمهنية. "
            "ضمّن المهام المكتملة والمتأخرة، الأنماط التي لاحظتها، ملخصًا ماليًا، "
            "العادات الصحية، العلاقات الاجتماعية، واقتراحات عملية للأسبوع القادم. "
            "كن بنّاءً ومباشرًا دون إطالة."
        )

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
                for tool_call in choice.message.tool_calls:
                    func_name = tool_call.function.name
                    try:
                        func_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        func_args = {}
                    tool_result = await self.handle_tool_call(func_name, func_args)
                    conversation.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result,
                        }
                    )

                response = await self._chat_completion_with_fallback(
                    messages=conversation,
                    tools=self.get_tools_schema(),
                    tool_choice="auto",
                    max_tokens=2500,
                    temperature=0.7,
                )
                return response.choices[0].message.content or ""

            return choice.message.content or ""
        except Exception as e:
            log.error(f"Weekly review generation failed: {e}")
            return "تعذر إعداد المراجعة الأسبوعية الآن. سأحاول مرة أخرى في الموعد القادم."
