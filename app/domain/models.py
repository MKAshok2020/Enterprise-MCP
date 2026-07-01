"""Pure domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Role:
    """A role assigned to users."""

    id: int
    name: str


@dataclass(frozen=True)
class Permission:
    """A permission grant."""

    id: int
    code: str
    description: str


@dataclass(frozen=True)
class User:
    """Authenticated enterprise user."""

    id: int
    username: str
    is_active: bool
    email: str | None = None
    display_name: str | None = None
    auth_source: str = "local"
    roles: tuple[Role, ...] = field(default_factory=tuple)
    permissions: tuple[Permission, ...] = field(default_factory=tuple)

    @property
    def role_names(self) -> set[str]:
        """Return assigned role names."""
        return {role.name for role in self.roles}

    @property
    def permission_codes(self) -> set[str]:
        """Return effective permission codes."""
        return {permission.code for permission in self.permissions}


@dataclass(frozen=True)
class ServerDefinition:
    """Configured MCP server connection definition."""

    name: str
    command: str
    args: tuple[str, ...]
    env: dict[str, str]
    allowed_roles: tuple[str, ...]
    timeout_seconds: int


@dataclass(frozen=True)
class ToolDefinition:
    """Tool discovered from an MCP server."""

    server_name: str
    name: str
    description: str
    input_schema: dict[str, Any]
    allowed_roles: tuple[str, ...] = field(default_factory=tuple)

    @property
    def qualified_name(self) -> str:
        """Return server-qualified tool name."""
        return f"{self.server_name}.{self.name}"


@dataclass(frozen=True)
class ResourceDefinition:
    """Resource discovered from an MCP server."""

    server_name: str
    uri: str
    name: str
    description: str
    mime_type: str | None


@dataclass(frozen=True)
class PromptDefinition:
    """Prompt discovered from an MCP server."""

    server_name: str
    name: str
    description: str
    arguments: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class AuthTokens:
    """Issued JWT access and refresh tokens."""

    access_token: str
    refresh_token: str
    expires_at: datetime


@dataclass(frozen=True)
class IdentityProvider:
    """Configured enterprise or third-party identity provider."""

    id: int
    name: str
    provider_type: str
    issuer_url: str | None
    client_id: str
    scopes: tuple[str, ...]
    is_active: bool


@dataclass(frozen=True)
class FederatedIdentityProfile:
    """Verified identity returned by an OAuth, OIDC, or SAML provider."""

    provider_name: str
    subject: str
    email: str
    display_name: str
    claims: dict[str, Any]


@dataclass
class UserSession:
    """Active authenticated user context."""

    session_id: str
    user: User
    tokens: AuthTokens
    created_at: datetime
    last_seen_at: datetime

    def touch(self) -> None:
        """Record session activity."""
        self.last_seen_at = datetime.now(timezone.utc)
