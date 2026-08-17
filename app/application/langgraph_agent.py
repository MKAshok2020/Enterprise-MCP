"""LangGraph-based orchestration for MCP tool execution and document retrieval."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any, TypedDict

from langchain_core.messages import ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app.application.document_store import DocumentStore
from app.application.tool_manager import ToolManager
from app.domain.exceptions import EnterpriseMCPError
from app.domain.models import ToolDefinition, User
from app.persistence.repositories import AccessRepository


class AgentState(TypedDict):
    """LangGraph state for a single chat turn."""

    messages: Annotated[list[Any], add_messages]


class LangGraphAgent:
    """Builds and executes the primary graph for LLM request orchestration."""

    def __init__(
        self,
        llm: Any,
        tool_specs: list[dict[str, Any]],
        alias_map: dict[str, ToolDefinition],
        tool_manager: ToolManager,
        document_store: DocumentStore,
        user: User,
        connections: dict[str, Any],
        access_repository: AccessRepository,
    ) -> None:
        self.llm = llm
        self.tool_specs = tool_specs
        self.alias_map = alias_map
        self.tool_manager = tool_manager
        self.document_store = document_store
        self.user = user
        self.connections = connections
        self.access_repository = access_repository
        self.tool_llm = llm.bind_tools(tool_specs) if tool_specs else llm

    def build_graph(self) -> Any:
        """Return the compiled LangGraph workflow used for chat execution."""
        graph = StateGraph(AgentState)
        graph.add_node("model", self.call_model)
        graph.add_node("tools", self.call_tools)
        graph.set_entry_point("model")
        graph.add_conditional_edges(
            "model",
            self.should_continue,
            {"tools": "tools", END: END},
        )
        graph.add_edge("tools", "model")
        return graph.compile()

    async def call_model(self, state: AgentState) -> dict[str, list[Any]]:
        """Ask the model for a response or tool call."""
        response = await self.tool_llm.ainvoke(state["messages"])
        return {"messages": [response]}

    async def call_tools(self, state: AgentState) -> dict[str, list[Any]]:
        """Execute each tool call issued by the model."""
        last_message = state["messages"][-1]
        tool_messages: list[ToolMessage] = []
        for tool_call in getattr(last_message, "tool_calls", []) or []:
            alias = tool_call.get("name", "")
            tool = self.alias_map.get(alias)
            args = tool_call.get("args") or {}
            if tool is None:
                content = json.dumps({"error": f"Unknown tool alias: {alias}"})
            elif tool.server_name == "local" and tool.name == "retrieve_documents":
                query = str(args.get("query", "")).strip()
                try:
                    result = await self._retrieve_documents(query)
                    content = self._json(result)
                except Exception as exc:  # pragma: no cover - defensive handling
                    content = self._json({"error": str(exc)})
            else:
                try:
                    result = await self.tool_manager.execute(
                        tool.qualified_name,
                        args,
                        self.user,
                        self.connections,
                        self.access_repository,
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

    def should_continue(self, state: AgentState) -> str:
        """Continue if the model produced tool calls, otherwise end."""
        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return END

    async def _retrieve_documents(self, query: str) -> list[dict[str, Any]]:
        """Search the knowledge base for relevant document snippets."""
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

    @staticmethod
    def _json(value: Any) -> str:
        """Serialize values as JSON for tool message content."""
        try:
            return json.dumps(value, default=str)
        except TypeError:
            return json.dumps(str(value))
