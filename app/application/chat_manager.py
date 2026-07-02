"""LLM chat orchestration with MCP tool use and document context."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any, TypedDict

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
    ) -> None:
        self.tool_manager = tool_manager
        self.document_store = document_store
        self.model_name = model_name

    async def respond(
        self,
        message: str,
        user: User,
        connections: dict[str, Any],
        access_repository: AccessRepository,
    ) -> dict[str, Any]:
        """Return an LLM response, optionally executing approved MCP tools."""
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
        from langchain_ollama import ChatOllama
        from langgraph.graph import END, StateGraph
        docs = self.document_store.search(message)
        tool_specs, alias_map = self._tool_schemas(user, access_repository)
        llm = ChatOllama(model=self.model_name, temperature=0.2)
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
                    SystemMessage(content=self._system_prompt(docs, tool_specs)),
                    HumanMessage(content=message),
                ]
            },
            {"recursion_limit": 8},
        )
        messages = result["messages"]
        final_answer = getattr(messages[-1], "content", "") or ""
        tool_events = self._tool_events(messages, alias_map)
        first_tool = tool_events[0] if tool_events else None
        return {
            "answer": final_answer,
            "tool": first_tool["tool"] if first_tool else None,
            "arguments": first_tool["arguments"] if first_tool else None,
            "result": first_tool["result"] if first_tool else None,
            "tools": tool_events,
            "documents": [
                {"filename": doc.filename, "score": doc.score, "text": doc.text}
                for doc in docs
            ],
        }

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

    def _system_prompt(self, docs: list[Any], tool_specs: list[dict[str, Any]]) -> str:
        document_context = "\n\n".join(
            f"Source: {doc.filename}\n{doc.text}" for doc in docs
        )
        tool_note = (
            "Use connected MCP tools when they are needed for live service data or actions."
            if tool_specs
            else "No MCP tools are currently available to you."
        )
        return (
            "You are an enterprise MCP chatbot. Answer naturally and concisely. "
            "When a tool result is returned, rephrase it for the user instead of dumping raw JSON. "
            "Do not claim you used a tool unless a tool call was actually made. "
            f"{tool_note}\n\n"
            "Use the following uploaded document excerpts only when relevant. "
            "If they are not relevant, ignore them.\n"
            f"{document_context or 'No relevant uploaded document excerpts.'}"
        )

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
