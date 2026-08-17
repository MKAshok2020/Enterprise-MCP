"""SQLAlchemy persistence entities."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base entity class."""


class UserEntity(Base):
    """Application user table."""

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_source: Mapped[str] = mapped_column(String(30), default="local")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    roles: Mapped[list[RoleEntity]] = relationship(
        secondary="user_roles", back_populates="users"
    )
    identities: Mapped[list[FederatedIdentityEntity]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RoleEntity(Base):
    """Role table."""

    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    users: Mapped[list[UserEntity]] = relationship(
        secondary="user_roles", back_populates="roles"
    )
    permissions: Mapped[list[PermissionEntity]] = relationship(
        secondary="role_permissions", back_populates="roles"
    )


class PermissionEntity(Base):
    """Permission table."""

    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(150), unique=True)
    description: Mapped[str] = mapped_column(String(255))
    roles: Mapped[list[RoleEntity]] = relationship(
        secondary="role_permissions", back_populates="permissions"
    )


class UserRoleEntity(Base):
    """User role link table."""

    __tablename__ = "user_roles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)


class IdentityProviderEntity(Base):
    """OAuth2, OIDC, and SAML provider configuration table."""

    __tablename__ = "identity_providers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    provider_type: Mapped[str] = mapped_column(String(30))
    issuer_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authorization_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    token_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    userinfo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    jwks_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    client_id: Mapped[str] = mapped_column(String(255))
    client_secret_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scopes: Mapped[str] = mapped_column(String(500), default="openid email profile")
    default_role: Mapped[str] = mapped_column(String(100), default="Viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    identities: Mapped[list[FederatedIdentityEntity]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )


class FederatedIdentityEntity(Base):
    """External identity linked to a local user."""

    __tablename__ = "federated_identities"
    __table_args__ = (
        UniqueConstraint("provider_id", "subject", name="uq_provider_subject"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("identity_providers.id"), index=True
    )
    subject: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claims_json: Mapped[str] = mapped_column(Text, default="{}")
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    user: Mapped[UserEntity] = relationship(back_populates="identities")
    provider: Mapped[IdentityProviderEntity] = relationship(back_populates="identities")


class SSOLoginSessionEntity(Base):
    """Tracks SSO login handshakes for OAuth/OIDC/SAML flows."""

    __tablename__ = "sso_login_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("identity_providers.id"))
    state: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    nonce: Mapped[str | None] = mapped_column(String(255), nullable=True)
    redirect_uri: Mapped[str] = mapped_column(String(500))
    code_verifier_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RolePermissionEntity(Base):
    """Role permission link table."""

    __tablename__ = "role_permissions"
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id"), primary_key=True
    )


class AuditLogEntity(Base):
    """Audit event table."""

    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45))
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    details: Mapped[str] = mapped_column(Text, default="")


class ChatMessageEntity(Base):
    """Persisted chat turns for later context reuse."""

    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    username: Mapped[str] = mapped_column(String(100), index=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class ServerAccessEntity(Base):
    """Server role access table."""

    __tablename__ = "server_access"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    server_name: Mapped[str] = mapped_column(String(150), index=True)
    role_name: Mapped[str] = mapped_column(String(100), index=True)


class ToolPermissionEntity(Base):
    """Tool role permission table."""

    __tablename__ = "tool_permissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tool_name: Mapped[str] = mapped_column(String(250), index=True)
    role_name: Mapped[str] = mapped_column(String(100), index=True)
