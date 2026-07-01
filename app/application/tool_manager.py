"""Tool discovery and execution manager."""

from typing import Any

from app.domain.enums import PermissionCode
from app.domain.exceptions import ServerUnavailableError
from app.domain.models import ToolDefinition, User
from app.persistence.repositories import AccessRepository
from app.security.authorization_service import AuthorizationService


class ToolManager:
    """Discovers and executes MCP tools."""

    def __init__(self, authorization: AuthorizationService) -> None:
        self.authorization = authorization
        self._tools: dict[str, ToolDefinition] = {}

    async def refresh(self, connections: dict[str, Any]) -> list[ToolDefinition]:
        """Refresh tools from all connected servers."""
        self._tools.clear()
        for connection in connections.values():
            for tool in await connection.list_tools():
                self._tools[tool.qualified_name] = tool
        return self.list_tools()

    def list_tools(self) -> list[ToolDefinition]:
        """Return discovered tools."""
        return list(self._tools.values())

    async def execute(
        self,
        qualified_name: str,
        arguments: dict[str, Any],
        user: User,
        connections: dict[str, Any],
        access_repository: AccessRepository,
    ) -> Any:
        """Authorize and execute a tool."""
        self.authorization.require_permission(user, PermissionCode.EXECUTE_TOOLS.value)
        tool = self._tools.get(qualified_name)
        if tool is None:
            raise ServerUnavailableError(f"Tool not discovered: {qualified_name}")
        self.authorization.require_tool_access(user, tool, access_repository)
        return await connections[tool.server_name].call_tool(tool.name, arguments)

