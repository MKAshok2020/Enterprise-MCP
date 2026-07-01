"""RBAC authorization service."""

from app.domain.exceptions import AuthorizationError
from app.domain.models import ServerDefinition, ToolDefinition, User
from app.persistence.repositories import AccessRepository


class AuthorizationService:
    """Evaluates permissions and role access rules."""

    def require_permission(self, user: User, permission_code: str) -> None:
        """Require an effective permission code."""
        if permission_code not in user.permission_codes:
            raise AuthorizationError(f"Permission denied: {permission_code}")

    def require_server_access(
        self,
        user: User,
        server: ServerDefinition,
        access_repository: AccessRepository,
    ) -> None:
        """Require role access for a server."""
        configured_roles = access_repository.server_roles(server.name)
        allowed_roles = configured_roles or set(server.allowed_roles)
        if allowed_roles and user.role_names.isdisjoint(allowed_roles):
            raise AuthorizationError(f"Access denied to server: {server.name}")

    def require_tool_access(
        self,
        user: User,
        tool: ToolDefinition,
        access_repository: AccessRepository,
    ) -> None:
        """Require role access for a tool."""
        configured_roles = access_repository.tool_roles(tool.qualified_name)
        fallback_roles = set(tool.allowed_roles)
        allowed_roles = configured_roles or fallback_roles
        if allowed_roles and user.role_names.isdisjoint(allowed_roles):
            raise AuthorizationError(f"Access denied to tool: {tool.qualified_name}")

