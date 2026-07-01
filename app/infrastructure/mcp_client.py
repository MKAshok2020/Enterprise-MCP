"""Official MCP SDK client adapter."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.domain.exceptions import ServerUnavailableError, ToolExecutionError
from app.domain.models import (
    PromptDefinition,
    ResourceDefinition,
    ServerDefinition,
    ToolDefinition,
)


class MCPServerConnection:
    """Active MCP server connection."""

    def __init__(self, server: ServerDefinition) -> None:
        self.server = server
        self.exit_stack = AsyncExitStack()
        self.session: ClientSession | None = None

    async def connect(self) -> None:
        """Connect to the configured MCP server."""
        params = StdioServerParameters(
            command=self.server.command,
            args=list(self.server.args),
            env=self.server.env,
        )
        try:
            read_stream, write_stream = await self.exit_stack.enter_async_context(
                stdio_client(params)
            )
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await self.session.initialize()
        except Exception as exc:
            await self.close()
            raise ServerUnavailableError(str(exc)) from exc

    async def close(self) -> None:
        """Close the MCP connection."""
        await self.exit_stack.aclose()
        self.session = None

    async def list_tools(self) -> list[ToolDefinition]:
        """Discover server tools."""
        session = self._require_session()
        result = await session.list_tools()
        return [self._tool(item) for item in result.tools]

    async def list_resources(self) -> list[ResourceDefinition]:
        """Discover server resources."""
        session = self._require_session()
        result = await session.list_resources()
        return [self._resource(item) for item in result.resources]

    async def list_prompts(self) -> list[PromptDefinition]:
        """Discover server prompts."""
        session = self._require_session()
        result = await session.list_prompts()
        return [self._prompt(item) for item in result.prompts]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool with timeout enforcement."""
        session = self._require_session()
        try:
            return await asyncio.wait_for(
                session.call_tool(name, arguments),
                timeout=self.server.timeout_seconds,
            )
        except Exception as exc:
            raise ToolExecutionError(str(exc)) from exc

    def _require_session(self) -> ClientSession:
        if self.session is None:
            raise ServerUnavailableError(f"{self.server.name} is not connected.")
        return self.session

    def _tool(self, item: Any) -> ToolDefinition:
        return ToolDefinition(
            server_name=self.server.name,
            name=item.name,
            description=getattr(item, "description", "") or "",
            input_schema=getattr(item, "inputSchema", {}) or {},
        )

    def _resource(self, item: Any) -> ResourceDefinition:
        return ResourceDefinition(
            server_name=self.server.name,
            uri=str(item.uri),
            name=getattr(item, "name", "") or str(item.uri),
            description=getattr(item, "description", "") or "",
            mime_type=getattr(item, "mimeType", None),
        )

    def _prompt(self, item: Any) -> PromptDefinition:
        return PromptDefinition(
            server_name=self.server.name,
            name=item.name,
            description=getattr(item, "description", "") or "",
            arguments=tuple(getattr(item, "arguments", []) or []),
        )

