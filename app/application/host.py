"""Application composition root."""

import logging
from time import perf_counter
from typing import Any

from app.config.settings import Settings, get_settings
from app.domain.enums import AuditEventType
from app.domain.models import User, UserSession
from app.infrastructure.configuration import ConfigurationLoader, DataSeeder
from app.infrastructure.logger import configure_logging
from app.persistence.database import Database
from app.persistence.repositories import AccessRepository, AuditLogRepository
from app.security.auth_service import AuthenticationService
from app.security.authorization_service import AuthorizationService
from app.security.jwt_service import JWTService
from app.security.password_service import PasswordService
from app.security.session_store import SessionStore
from app.security.sso_service import SSOService
from app.application.prompt_manager import PromptManager
from app.application.resource_manager import ResourceManager
from app.application.server_manager import ServerManager
from app.application.session_manager import SessionManager
from app.application.chat_manager import ChatManager
from app.application.tool_manager import ToolManager


class Host:
    """Coordinates enterprise MCP host services."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.logger = configure_logging(self.settings)
        self.database = Database(self.settings)
        self.passwords = PasswordService()
        self.jwt = JWTService(self.settings)
        self.sessions = SessionStore(self.settings)
        self.auth = AuthenticationService(self.passwords, self.jwt, self.sessions)
        self.sso = SSOService()
        self.authorization = AuthorizationService()
        self.session_manager = SessionManager(self.sessions)
        self.loader = ConfigurationLoader(self.settings)
        self.servers, self.tool_rules, self.identity_providers = self.loader.load()
        self.server_manager = ServerManager(self.servers, self.authorization)
        self.tool_manager = ToolManager(self.authorization)
        self.chat_manager = ChatManager(self.tool_manager)
        self.resource_manager = ResourceManager()
        self.prompt_manager = PromptManager()

    def initialize(self) -> None:
        """Create schema and seed enterprise defaults."""
        self.database.create_schema()
        with self.database.session() as session:
            from app.persistence.repositories import RoleRepository, UserRepository
            seeder = DataSeeder(self.passwords)
            seeder.seed(
                UserRepository(session),
                RoleRepository(session),
                AccessRepository(session),
                self.servers,
                self.tool_rules,
                self.identity_providers,
            )

    def login(self, username: str, password: str) -> UserSession:
        """Authenticate and set the current session."""
        start = perf_counter()
        try:
            with self.database.session() as session:
                from app.persistence.repositories import UserRepository
                user_session = self.auth.login(username, password, UserRepository(session))
            self.session_manager.set_current(user_session)
            self.audit_duration(
                AuditEventType.LOGIN.value, username, True, "Login succeeded", start
            )
            return user_session
        except Exception as exc:
            self.audit_duration(AuditEventType.AUTH_FAILURE.value, username, False, str(exc), start)
            raise

    def logout(self) -> None:
        """Logout the current user."""
        session = self.session_manager.current()
        self.auth.logout(session.session_id)
        self.audit(AuditEventType.LOGOUT.value, session.user.username, True, "Logout")
        self.session_manager.clear()

    async def refresh_discovery(self, user: User | None = None) -> None:
        """Refresh tools, resources, and prompts."""
        connections = self.server_manager.connections
        await self.tool_manager.refresh(connections)
        await self.resource_manager.refresh(connections)
        await self.prompt_manager.refresh(connections)
        audit_user = user or self.session_manager.current().user
        self.audit(AuditEventType.SERVER_REFRESH.value, audit_user.username, True, "Refreshed")

    def audit(self, event: str, username: str | None, success: bool, details: str) -> None:
        """Write an audit record."""
        with self.database.session() as session:
            AuditLogRepository(session).add(
                event, username, self.settings.audit_ip_placeholder, success, details
            )

    def audit_duration(
        self,
        event: str,
        username: str | None,
        success: bool,
        details: str,
        start: float,
    ) -> None:
        """Write an audit record with duration."""
        duration_ms = int((perf_counter() - start) * 1000)
        with self.database.session() as session:
            AuditLogRepository(session).add(
                event,
                username,
                self.settings.audit_ip_placeholder,
                success,
                details,
                duration_ms,
            )
        logging.getLogger("enterprise_mcp_host").info("%s %s", event, details)

    def audit_logs(self, limit: int = 100) -> list[Any]:
        """Return recent audit logs."""
        with self.database.session() as session:
            return AuditLogRepository(session).latest(limit)

    async def shutdown(self) -> None:
        """Gracefully close connected servers."""
        await self.server_manager.shutdown()
