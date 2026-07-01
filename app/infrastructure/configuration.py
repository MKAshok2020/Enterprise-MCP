"""JSON configuration loading and database seeding."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config.settings import Settings
from app.domain.enums import PermissionCode
from app.domain.exceptions import ConfigurationError
from app.domain.models import ServerDefinition
from app.persistence.repositories import AccessRepository, RoleRepository, UserRepository
from app.security.password_service import PasswordService


class ConfigurationLoader:
    """Loads server and permission configuration."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def load(
        self,
    ) -> tuple[list[ServerDefinition], dict[str, tuple[str, ...]], list[dict[str, object]]]:
        """Load configured servers and tool permission metadata."""
        data = self._read_json(self.settings.servers_config_path)
        servers = [self._server_from_dict(item) for item in data.get("servers", [])]
        tool_rules = {
            key: tuple(value) for key, value in data.get("tool_permissions", {}).items()
        }
        providers = list(data.get("identity_providers", []))
        return servers, tool_rules, providers

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ConfigurationError(f"Configuration not found: {path}")
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _server_from_dict(self, item: dict[str, Any]) -> ServerDefinition:
        required = {"name", "command", "args", "env", "allowed_roles"}
        if missing := required.difference(item):
            raise ConfigurationError(f"Server config missing: {sorted(missing)}")
        return ServerDefinition(
            name=str(item["name"]),
            command=str(item["command"]),
            args=tuple(str(arg) for arg in item["args"]),
            env={str(key): str(value) for key, value in item["env"].items()},
            allowed_roles=tuple(str(role) for role in item["allowed_roles"]),
            timeout_seconds=int(item.get("timeout_seconds", 30)),
        )


class DataSeeder:
    """Seeds enterprise defaults idempotently."""

    ROLE_PERMISSIONS = {
        "Administrator": tuple(code.value for code in PermissionCode),
        "Operator": (
            PermissionCode.CONNECT_SERVERS.value,
            PermissionCode.EXECUTE_TOOLS.value,
            PermissionCode.LIST_TOOLS.value,
            PermissionCode.LIST_RESOURCES.value,
            PermissionCode.LIST_SERVERS.value,
        ),
        "Viewer": (
            PermissionCode.LIST_SERVERS.value,
            PermissionCode.LIST_TOOLS.value,
            PermissionCode.LIST_RESOURCES.value,
            PermissionCode.VIEW_PROMPTS.value,
        ),
    }
    DEFAULT_USERS = (
        ("admin", "admin@example.com", "Admin@123", "Administrator"),
        ("operator", "operator@example.com", "Operator@123", "Operator"),
        ("viewer", "viewer@example.com", "Viewer@123", "Viewer"),
    )

    def __init__(self, password_service: PasswordService) -> None:
        self.password_service = password_service

    def seed(
        self,
        users: UserRepository,
        roles: RoleRepository,
        access: AccessRepository,
        servers: list[ServerDefinition],
        tool_rules: dict[str, tuple[str, ...]],
        identity_providers: list[dict[str, object]],
    ) -> None:
        """Seed users, roles, permissions, and access rules."""
        from app.persistence.repositories import IdentityRepository

        for role_name, permission_codes in self.ROLE_PERMISSIONS.items():
            role = users.get_or_create_role(role_name)
            roles.assign_permissions(role, permission_codes)
        for username, email, password, role_name in self.DEFAULT_USERS:
            self._ensure_user(users, username, email, password, role_name)
        for server in servers:
            access.replace_server_access(server.name, server.allowed_roles)
        for tool_name, allowed_roles in tool_rules.items():
            access.replace_tool_permissions(tool_name, allowed_roles)
        identities = IdentityRepository(users.session)
        for provider in identity_providers:
            identities.upsert_provider(provider)

    def _ensure_user(
        self,
        users: UserRepository,
        username: str,
        email: str,
        password: str,
        role_name: str,
    ) -> None:
        entity = users.find_by_username(username)
        if entity is None:
            entity = users.create_user(
                username,
                self.password_service.hash_password(password),
                email=email,
                display_name=username.title(),
                auth_source="local",
            )
        users.assign_role(entity, role_name)
