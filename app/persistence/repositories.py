"""Repository implementations."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.models import FederatedIdentityProfile, Permission, Role, User
from app.persistence.entities import (
    AuditLogEntity,
    FederatedIdentityEntity,
    IdentityProviderEntity,
    PermissionEntity,
    RoleEntity,
    ServerAccessEntity,
    SSOLoginSessionEntity,
    ToolPermissionEntity,
    UserEntity,
)


def to_domain_user(entity: UserEntity) -> User:
    """Map a user entity to a domain user."""
    permissions = {
        permission
        for role in entity.roles
        for permission in role.permissions
    }
    return User(
        id=entity.id,
        username=entity.username,
        is_active=entity.is_active,
        email=entity.email,
        display_name=entity.display_name,
        auth_source=entity.auth_source,
        roles=tuple(Role(role.id, role.name) for role in entity.roles),
        permissions=tuple(
            Permission(item.id, item.code, item.description) for item in permissions
        ),
    )


class UserRepository:
    """Repository for users and role assignments."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_username(self, username: str) -> UserEntity | None:
        """Return a user entity by username."""
        statement = (
            select(UserEntity)
            .options(selectinload(UserEntity.roles).selectinload(RoleEntity.permissions))
            .where(UserEntity.username == username)
        )
        return self.session.scalar(statement)

    def find_by_email(self, email: str) -> UserEntity | None:
        """Return a user entity by email."""
        statement = (
            select(UserEntity)
            .options(selectinload(UserEntity.roles).selectinload(RoleEntity.permissions))
            .where(UserEntity.email == email)
        )
        return self.session.scalar(statement)

    def list_users(self) -> list[User]:
        """Return all users."""
        statement = select(UserEntity).options(
            selectinload(UserEntity.roles).selectinload(RoleEntity.permissions)
        )
        return [to_domain_user(entity) for entity in self.session.scalars(statement)]

    def create_user(
        self,
        username: str,
        password_hash: str | None,
        email: str | None = None,
        display_name: str | None = None,
        auth_source: str = "local",
    ) -> UserEntity:
        """Create a new user entity."""
        user = UserEntity(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            auth_source=auth_source,
        )
        self.session.add(user)
        self.session.flush()
        return user

    def mark_login(self, user: UserEntity) -> None:
        """Record a successful user login."""
        user.last_login_at = datetime.now(timezone.utc)

    def assign_role(self, user: UserEntity, role_name: str) -> None:
        """Assign a role to a user."""
        role = self.get_or_create_role(role_name)
        if role not in user.roles:
            user.roles.append(role)

    def get_or_create_role(self, role_name: str) -> RoleEntity:
        """Return a role, creating it when absent."""
        role = self.session.scalar(select(RoleEntity).where(RoleEntity.name == role_name))
        if role is None:
            role = RoleEntity(name=role_name)
            self.session.add(role)
            self.session.flush()
        return role


class RoleRepository:
    """Repository for roles and permissions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_permission(self, code: str, description: str) -> PermissionEntity:
        """Return a permission, creating it when absent."""
        query = select(PermissionEntity).where(PermissionEntity.code == code)
        permission = self.session.scalar(query)
        if permission is None:
            permission = PermissionEntity(code=code, description=description)
            self.session.add(permission)
            self.session.flush()
        return permission

    def assign_permissions(self, role: RoleEntity, codes: Iterable[str]) -> None:
        """Assign permission codes to a role."""
        for code in codes:
            permission = self.get_or_create_permission(code, code.replace(".", " "))
            if permission not in role.permissions:
                role.permissions.append(permission)

    def list_roles(self) -> list[Role]:
        """Return all roles."""
        return [Role(role.id, role.name) for role in self.session.scalars(select(RoleEntity))]


class IdentityRepository:
    """Repository for identity providers and federated accounts."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_provider(self, name: str) -> IdentityProviderEntity | None:
        """Return an identity provider by name."""
        return self.session.scalar(
            select(IdentityProviderEntity).where(IdentityProviderEntity.name == name)
        )

    def upsert_provider(self, data: dict[str, str | bool]) -> IdentityProviderEntity:
        """Create or update an identity provider."""
        provider = self.get_provider(str(data["name"]))
        if provider is None:
            provider = IdentityProviderEntity(
                name=str(data["name"]),
                provider_type=str(data["provider_type"]),
                client_id=str(data["client_id"]),
            )
            self.session.add(provider)
        for key, value in data.items():
            if hasattr(provider, key):
                setattr(provider, key, value)
        self.session.flush()
        return provider

    def find_identity(
        self,
        provider_name: str,
        subject: str,
    ) -> FederatedIdentityEntity | None:
        """Return a linked federated identity."""
        statement = (
            select(FederatedIdentityEntity)
            .join(IdentityProviderEntity)
            .options(
                selectinload(FederatedIdentityEntity.user)
                .selectinload(UserEntity.roles)
                .selectinload(RoleEntity.permissions)
            )
            .where(IdentityProviderEntity.name == provider_name)
            .where(FederatedIdentityEntity.subject == subject)
        )
        return self.session.scalar(statement)

    def link_identity(
        self,
        user: UserEntity,
        provider: IdentityProviderEntity,
        profile: FederatedIdentityProfile,
    ) -> FederatedIdentityEntity:
        """Link an external provider identity to a local user."""
        identity = self.find_identity(provider.name, profile.subject)
        if identity is None:
            identity = FederatedIdentityEntity(
                user=user,
                provider=provider,
                subject=profile.subject,
                email=profile.email,
            )
            self.session.add(identity)
        identity.email = profile.email
        identity.display_name = profile.display_name
        identity.claims_json = json.dumps(profile.claims, sort_keys=True)
        identity.last_login_at = datetime.now(timezone.utc)
        self.session.flush()
        return identity

    def create_sso_session(
        self,
        provider: IdentityProviderEntity,
        state: str,
        redirect_uri: str,
        expires_at: datetime,
        nonce: str | None = None,
        code_verifier_hash: str | None = None,
    ) -> SSOLoginSessionEntity:
        """Create an SSO login handshake session."""
        session = SSOLoginSessionEntity(
            provider_id=provider.id,
            state=state,
            nonce=nonce,
            redirect_uri=redirect_uri,
            code_verifier_hash=code_verifier_hash,
            expires_at=expires_at,
        )
        self.session.add(session)
        self.session.flush()
        return session


class AuditLogRepository:
    """Repository for audit events."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        event_type: str,
        username: str | None,
        ip_address: str,
        success: bool,
        details: str,
        duration_ms: int | None = None,
    ) -> None:
        """Persist an audit event."""
        self.session.add(AuditLogEntity(
            event_type=event_type,
            username=username,
            ip_address=ip_address,
            success=success,
            details=details,
            duration_ms=duration_ms,
        ))

    def latest(self, limit: int = 100) -> list[AuditLogEntity]:
        """Return latest audit logs."""
        statement = select(AuditLogEntity).order_by(AuditLogEntity.id.desc()).limit(limit)
        return list(self.session.scalars(statement))


class AccessRepository:
    """Repository for server and tool access rules."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_server_access(self, server_name: str, roles: Iterable[str]) -> None:
        """Replace server role access rules."""
        self.session.query(ServerAccessEntity).filter_by(server_name=server_name).delete()
        for role in roles:
            self.session.add(ServerAccessEntity(server_name=server_name, role_name=role))

    def replace_tool_permissions(self, tool_name: str, roles: Iterable[str]) -> None:
        """Replace tool role access rules."""
        self.session.query(ToolPermissionEntity).filter_by(tool_name=tool_name).delete()
        for role in roles:
            self.session.add(ToolPermissionEntity(tool_name=tool_name, role_name=role))

    def server_roles(self, server_name: str) -> set[str]:
        """Return roles allowed to access a server."""
        query = select(ServerAccessEntity.role_name).where(
            ServerAccessEntity.server_name == server_name
        )
        return set(self.session.scalars(query))

    def tool_roles(self, tool_name: str) -> set[str]:
        """Return roles allowed to execute a tool."""
        query = select(ToolPermissionEntity.role_name).where(
            ToolPermissionEntity.tool_name == tool_name
        )
        return set(self.session.scalars(query))
