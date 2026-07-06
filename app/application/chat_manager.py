"""LLM chat orchestration with MCP tool use and document context."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Annotated, Any, TypedDict

logger = logging.getLogger("enterprise_mcp_host")

from langgraph.graph.message import add_messages

from app.application.document_store import DocumentStore
from app.application.tool_manager import ToolManager
from app.domain.exceptions import AuthorizationError, EnterpriseMCPError
from app.domain.models import ToolDefinition, User
from app.persistence.repositories import AccessRepository


class AgentState(TypedDict):
    """LangGraph state for a single chat turn."""

    messages: Annotated[list[Any], add_messages]


class ChatManager:
    """Runs a local Ollama LLM that can call authorized MCP tools."""

    def __init__(
        self,
        tool_manager: ToolManager,
        document_store: DocumentStore,
        model_name: str,
        base_url: str | None = None,
    ) -> None:
        self.tool_manager = tool_manager
        self.document_store = document_store
        self.model_name = model_name
        self.base_url = base_url
        self._llm: Any | None = None
        self._llm_lock = asyncio.Lock()

    async def respond(
        self,
        message: str,
        user: User,
        connections: dict[str, Any],
        access_repository: AccessRepository,
    ) -> dict[str, Any]:
        """Return an LLM response, optionally executing approved MCP tools."""
        logger.info("Chat request received from user %s.", user.username)
        normalized = message.strip()
        if not normalized:
            return {
                "answer": "Ask a question and I will use connected services or uploaded documents when they help.",
                "tool": None,
                "arguments": None,
                "result": None,
                "documents": [],
            }

        try:
            return await self._run_agent(
                normalized,
                user,
                connections,
                access_repository,
            )
        except ImportError as exc:
            return {
                "answer": (
                    "The LLM chat dependencies are not installed yet. Run "
                    "`pip install -r requirements.txt`, then restart the web app."
                ),
                "tool": None,
                "arguments": None,
                "result": str(exc),
                "documents": [],
            }
        except Exception as exc:
            logger.exception("Chat request failed for user %s.", user.username)
            return {
                "answer": f"The local LLM could not complete the chat request: {exc}",
                "tool": None,
                "arguments": None,
                "result": str(exc),
                "documents": [],
            }

    async def _run_agent(
        self,
        message: str,
        user: User,
        connections: dict[str, Any],
        access_repository: AccessRepository,
    ) -> dict[str, Any]:
        from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
        from langgraph.graph import END, StateGraph
        tool_specs, alias_map = self._tool_schemas(user, access_repository)
        llm = await self._get_llm()
        tool_llm = llm.bind_tools(tool_specs) if tool_specs else llm

        async def call_model(state: AgentState) -> dict[str, list[Any]]:
            response = await tool_llm.ainvoke(state["messages"])
            return {"messages": [response]}

        async def call_tools(state: AgentState) -> dict[str, list[Any]]:
            last_message = state["messages"][-1]
            tool_messages = []
            for tool_call in getattr(last_message, "tool_calls", []) or []:
                alias = tool_call.get("name", "")
                tool = alias_map.get(alias)
                args = tool_call.get("args") or {}
                if tool is None:
                    content = json.dumps({"error": f"Unknown tool alias: {alias}"})
                elif tool.server_name == "local" and tool.name == "retrieve_documents":
                    query = str(args.get("query", "")).strip()
                    try:
                        result = await self._retrieve_documents(query)
                        content = self._json(result)
                    except Exception as exc:
                        content = self._json({"error": str(exc)})
                else:
                    try:
                        result = await self.tool_manager.execute(
                            tool.qualified_name,
                            args,
                            user,
                            connections,
                            access_repository,
                        )
                        content = self._json(result)
                    except EnterpriseMCPError as exc:
                        content = self._json({"error": str(exc)})
                tool_messages.append(
                    ToolMessage(
                        content=content,
                        name=alias,
                        tool_call_id=tool_call.get("id", alias),
                    )
                )
            return {"messages": tool_messages}

        def should_continue(state: AgentState) -> str:
            last_message = state["messages"][-1]
            if getattr(last_message, "tool_calls", None):
                return "tools"
            return END

        graph = StateGraph(AgentState)
        graph.add_node("model", call_model)
        graph.add_node("tools", call_tools)
        graph.set_entry_point("model")
        graph.add_conditional_edges("model", should_continue, {"tools": "tools", END: END})
        graph.add_edge("tools", "model")
        app = graph.compile()

        result = await app.ainvoke(
            {
                "messages": [
                    SystemMessage(
                        content=self._system_prompt(tool_specs)
                    ),
                    HumanMessage(content=message),
                ]
            },
            {"recursion_limit": 8},
        )
        messages = result["messages"]
        final_answer = getattr(messages[-1], "content", "") or ""
        tool_events = self._tool_events(messages, alias_map)
        if not tool_events and alias_map:
            fallback_event = await self._select_and_execute_tool(
                llm,
                message,
                alias_map,
                user,
                connections,
                access_repository,
            )
            if fallback_event is not None:
                tool_events.append(fallback_event)
                final_answer = await self._rephrase_tool_result(
                    llm,
                    message,
                    fallback_event["tool"],
                    fallback_event["result"],
                )
        first_tool = tool_events[0] if tool_events else None
        retrieved_documents: list[dict[str, Any]] = []
        for event in tool_events:
            if event.get("tool") == "local.retrieve_documents" and isinstance(event.get("result"), list):
                retrieved_documents = event["result"]
                break
        return {
            "answer": final_answer,
            "tool": first_tool["tool"] if first_tool else None,
            "arguments": first_tool["arguments"] if first_tool else None,
            "result": first_tool["result"] if first_tool else None,
            "tools": tool_events,
            "documents": retrieved_documents,
        }

    async def _get_llm(self) -> Any:
        """Lazily create and cache the chat LLM instance."""
        async with self._llm_lock:
            if self._llm is None:
                from langchain_ollama import ChatOllama

                self._llm = ChatOllama(
                    model=self.model_name,
                    temperature=0.2,
                    base_url=self.base_url,
                )
        return self._llm

    async def _retrieve_documents(self, query: str) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        chunks = await asyncio.to_thread(self.document_store.search, query)
        return [
            {
                "document_id": chunk.document_id,
                "filename": chunk.filename,
                "score": chunk.score,
                "text": chunk.text,
            }
            for chunk in chunks
        ]

    async def _select_and_execute_tool(
        self,
        llm: Any,
        message: str,
        alias_map: dict[str, ToolDefinition],
        user: User,
        connections: dict[str, Any],
        access_repository: AccessRepository,
    ) -> dict[str, Any] | None:
        """Ask the LLM to select a registered tool when native tool calls are missed."""
        from langchain_core.messages import HumanMessage, SystemMessage

        selection_response = await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "You select connected API tools for an enterprise chatbot. "
                        "Return only JSON with this shape: "
                        '{"tool": "tool alias or none", "arguments": {}}. '
                        "Choose a tool only when the user needs live service data or an action. "
                        "Use only aliases from the available tools. If no tool is appropriate, "
                        'return {"tool": "none", "arguments": {}}.'
                    )
                ),
                HumanMessage(
                    content=(
                        f"User message: {message}\n\n"
                        f"{self._tool_selection_catalog(alias_map)}"
                    )
                ),
            ]
        )
        selection = self._parse_json_object(getattr(selection_response, "content", ""))
        alias = str(selection.get("tool", "")).strip()
        if not alias or alias.lower() == "none":
            return None

        tool = alias_map.get(alias)
        if tool is None:
            return None

        arguments = selection.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {}

        try:
            result = await self.tool_manager.execute(
                tool.qualified_name,
                arguments,
                user,
                connections,
                access_repository,
            )
        except EnterpriseMCPError as exc:
            result = {"error": str(exc)}

        return {
            "tool": tool.qualified_name,
            "arguments": arguments,
            "result": result,
        }

    async def _rephrase_tool_result(
        self,
        llm: Any,
        user_message: str,
        tool_name: str,
        result: Any,
    ) -> str:
        """Ask the LLM to turn a connected service response into chat text."""
        from langchain_core.messages import HumanMessage, SystemMessage

        response = await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "You are an enterprise MCP chatbot. Rephrase connected API "
                        "results into a concise, natural answer. Do not dump raw JSON. "
                        "If the API returned an error, explain the issue plainly."
                    )
                ),
                HumanMessage(
                    content=(
                        f"User message: {user_message}\n"
                        f"Tool used: {tool_name}\n"
                        f"Tool result: {self._json(result)}"
                    )
                ),
            ]
        )
        return getattr(response, "content", "") or self._json(result)

    def _tool_schemas(
        self,
        user: User,
        access_repository: AccessRepository,
    ) -> tuple[list[dict[str, Any]], dict[str, ToolDefinition]]:
        schemas = []
        alias_map = {}
        for index, tool in enumerate(self.tool_manager.list_tools(), start=1):
            if not self._can_use_tool(user, tool, access_repository):
                continue
            alias = self._tool_alias(index, tool)
            alias_map[alias] = tool
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": alias,
                        "description": (
                            f"{tool.qualified_name}: "
                            f"{tool.description or 'Invoke this connected service.'}"
                        ),
                        "parameters": self._parameters(tool.input_schema),
                    },
                }
            )
        retrieval_alias = "retrieve_documents"
        retrieval_tool = ToolDefinition(
            server_name="local",
            name="retrieve_documents",
            description="Search uploaded document excerpts for relevant evidence.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Text to search for relevant document excerpts.",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        )
        alias_map[retrieval_alias] = retrieval_tool
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": retrieval_alias,
                    "description": retrieval_tool.description,
                    "parameters": retrieval_tool.input_schema,
                },
            }
        )
        return schemas, alias_map

    def _can_use_tool(
        self,
        user: User,
        tool: ToolDefinition,
        access_repository: AccessRepository,
    ) -> bool:
        try:
            self.tool_manager.authorization.require_permission(user, "tools.execute")
            self.tool_manager.authorization.require_tool_access(user, tool, access_repository)
            return True
        except AuthorizationError:
            return False

    def _parameters(self, schema: dict[str, Any]) -> dict[str, Any]:
        if schema.get("type") == "object":
            return schema
        return {
            "type": "object",
            "additionalProperties": True,
            "properties": {},
        }

    def _tool_alias(self, index: int, tool: ToolDefinition) -> str:
        raw = f"{tool.server_name}_{tool.name}".lower()
        slug = re.sub(r"[^a-z0-9_-]+", "_", raw).strip("_")
        return f"tool_{index}_{slug}"[:64]

    def _system_prompt(
        self,
        tool_specs: list[dict[str, Any]],
    ) -> str:
        tool_catalog = self._tool_catalog(tool_specs)
        tool_note = (
            "Use connected MCP tools when they are needed for live service data or actions. "
            "Choose the best matching tool from the available tool list and supply only arguments "
            "that match its JSON schema."
            if tool_specs
            else "No MCP tools are currently available to you."
        )
        return (
            "You are an enterprise MCP chatbot. Answer naturally and concisely. "
            "When a tool result is returned, rephrase it for the user instead of dumping raw JSON. "
            "Do not claim you used a tool unless a tool call was actually made. "
            f"{tool_note}\n\n"
            f"{tool_catalog}\n\n"
            "If the user question requires uploaded document evidence, call the "
            'retrieve_documents(query={"query": "..."}) tool first rather than using document biology directly.'
        )

    def _tool_catalog(self, tool_specs: list[dict[str, Any]]) -> str:
        if not tool_specs:
            return "Available tools: none."
        lines = ["Available tools:"]
        for spec in tool_specs:
            function = spec.get("function", {})
            parameters = function.get("parameters", {})
            lines.append(
                "- "
                f"{function.get('name')}: {function.get('description', '')} "
                f"Parameters: {self._json(parameters)}"
            )
        return "\n".join(lines)

    def _tool_selection_catalog(self, alias_map: dict[str, ToolDefinition]) -> str:
        lines = ["Available tools:"]
        for alias, tool in alias_map.items():
            lines.append(
                "- "
                f"alias: {alias}\n"
                f"  service tool: {tool.qualified_name}\n"
                f"  description: {tool.description or 'Invoke this connected service.'}\n"
                f"  input schema: {self._json(self._parameters(tool.input_schema))}"
            )
        return "\n".join(lines)

    def _tool_events(
        self,
        messages: list[Any],
        alias_map: dict[str, ToolDefinition],
    ) -> list[dict[str, Any]]:
        events = []
        pending: dict[str, dict[str, Any]] = {}
        for message in messages:
            for tool_call in getattr(message, "tool_calls", []) or []:
                alias = tool_call.get("name", "")
                tool = alias_map.get(alias)
                pending[tool_call.get("id", alias)] = {
                    "tool": tool.qualified_name if tool else alias,
                    "arguments": tool_call.get("args") or {},
                    "result": None,
                }
            if message.__class__.__name__ == "ToolMessage":
                event = pending.get(getattr(message, "tool_call_id", ""))
                if event is not None:
                    event["result"] = self._parse_json(getattr(message, "content", ""))
                    events.append(event)
        return events

    def _json(self, value: Any) -> str:
        try:
            return json.dumps(value, default=str)
        except TypeError:
            return json.dumps(str(value))

    def _parse_json(self, value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    def _parse_json_object(self, value: str) -> dict[str, Any]:
        cleaned = value.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL)
        if fenced:
            cleaned = fenced.group(1).strip()
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if not match:
                return {}
            try:
                parsed = json.loads(match.group(0))
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
