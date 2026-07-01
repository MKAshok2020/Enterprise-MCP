"""Official MCP SDK client adapter."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.domain.enums import Protocol
from app.domain.exceptions import ServerUnavailableError, ToolExecutionError
from app.domain.models import (
    PromptDefinition,
    ResourceDefinition,
    ServerDefinition,
    ToolDefinition,
)
from app.services.adapters.base.base_adapter import BaseAdapter
from app.services.adapters.rest_adapter import RestAdapter
from app.services.factory.service_factory import ServiceFactory


class MCPServerConnection:
    """Active MCP server connection."""

    def __init__(
        self,
        server: ServerDefinition,
        service_factory: ServiceFactory | None = None,
    ) -> None:
        self.server = server
        self.exit_stack = AsyncExitStack()
        self.session: ClientSession | None = None
        self.service_adapter: BaseAdapter | None = None
        self.service_factory = service_factory or ServiceFactory(
            {
                Protocol.HTTP: RestAdapter,
                Protocol.HTTPS: RestAdapter,
                Protocol.REST: RestAdapter,
                Protocol.HTTP.value: RestAdapter,
                Protocol.HTTPS.value: RestAdapter,
                Protocol.REST.value: RestAdapter,
            }
        )

    async def connect(self) -> None:
        """Connect to the configured MCP server."""
        if self.server.service is not None:
            try:
                self.service_adapter = self.service_factory.get_service(
                    self.server.service
                )
                await self.service_adapter.connect()
                return
            except Exception as exc:
                await self.close()
                raise ServerUnavailableError(str(exc)) from exc

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
        if self.service_adapter is not None:
            await self.service_adapter.close()
            self.service_adapter = None
        await self.exit_stack.aclose()
        self.session = None

    async def list_tools(self) -> list[ToolDefinition]:
        """Discover server tools."""
        if self.server.service is not None:
            return [
                self._service_tool(name, operation)
                for name, operation in self.server.service.operations.items()
            ]

        session = self._require_session()
        result = await session.list_tools()
        return [self._tool(item) for item in result.tools]

    async def list_resources(self) -> list[ResourceDefinition]:
        """Discover server resources."""
        if self.server.service is not None:
            return []

        session = self._require_session()
        result = await session.list_resources()
        return [self._resource(item) for item in result.resources]

    async def list_prompts(self) -> list[PromptDefinition]:
        """Discover server prompts."""
        if self.server.service is not None:
            return []

        session = self._require_session()
        result = await session.list_prompts()
        return [self._prompt(item) for item in result.prompts]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool with timeout enforcement."""
        if self.server.service is not None:
            adapter = self._require_service_adapter()
            try:
                return await asyncio.wait_for(
                    adapter.invoke(name, arguments),
                    timeout=self.server.timeout_seconds,
                )
            except Exception as exc:
                raise ToolExecutionError(str(exc)) from exc

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

    def _require_service_adapter(self) -> BaseAdapter:
        if self.service_adapter is None:
            raise ServerUnavailableError(f"{self.server.name} is not connected.")
        return self.service_adapter

    def _tool(self, item: Any) -> ToolDefinition:
        return ToolDefinition(
            server_name=self.server.name,
            name=item.name,
            description=getattr(item, "description", "") or "",
            input_schema=getattr(item, "inputSchema", {}) or {},
        )

    def _service_tool(self, name: str, operation: Any) -> ToolDefinition:
        return ToolDefinition(
            server_name=self.server.name,
            name=name,
            description=operation.properties.get("description")
            or f"Invoke {self.server.name}.{name}",
            input_schema=operation.properties.get("inputSchema")
            or {
                "type": "object",
                "additionalProperties": True,
                "properties": {},
            },
            allowed_roles=self.server.allowed_roles,
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
