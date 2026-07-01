"""Rich CLI menu controller."""

from __future__ import annotations

from time import perf_counter

from rich.console import Console
from rich.prompt import Confirm, Prompt

from app.application.host import Host
from app.domain.enums import AuditEventType, PermissionCode
from app.domain.exceptions import AuthorizationError, EnterpriseMCPError
from app.persistence.repositories import AccessRepository
from app.presentation.renderer import Renderer
from app.presentation.screens import MenuScreen
from app.utils.validators import parse_json_object


class MenuController:
    """Handles CLI menu commands."""

    def __init__(self, host: Host, console: Console) -> None:
        self.host = host
        self.console = console
        self.renderer = Renderer(console)
        self.menu = MenuScreen(console)

    async def run(self) -> bool:
        """Run the menu until logout or exit."""
        while True:
            self._render_status()
            choice = self.menu.choice()
            if choice == "0":
                return False
            if choice == "9":
                self.host.logout()
                return True
            await self._dispatch(choice)

    async def _dispatch(self, choice: str) -> None:
        actions = {
            "1": self._servers,
            "2": self._tools,
            "3": self._resources,
            "4": self._prompts,
            "5": self._execute_tool,
            "6": self._administration,
            "7": self._audit_logs,
            "8": self._refresh,
        }
        try:
            await actions[choice]()
        except AuthorizationError as exc:
            user = self.host.session_manager.current().user
            self.host.audit(
                AuditEventType.PERMISSION_DENIED.value, user.username, False, str(exc)
            )
            self.renderer.message(str(exc), "red")
        except (EnterpriseMCPError, ValueError) as exc:
            user = self.host.session_manager.current().user
            self.host.audit(AuditEventType.ERROR.value, user.username, False, str(exc))
            self.renderer.message(str(exc), "red")

    def _render_status(self) -> None:
        session = self.host.session_manager.current()
        self.renderer.status(
            session.user.username,
            session.user.role_names,
            self.host.server_manager.connected_names(),
            len(self.host.tool_manager.list_tools()),
        )

    async def _servers(self) -> None:
        user = self.host.session_manager.current().user
        self.host.authorization.require_permission(user, PermissionCode.LIST_SERVERS.value)
        for server in self.host.server_manager.list_servers():
            connected = server.name in self.host.server_manager.connections
            self.console.print(f"{server.name} [{'connected' if connected else 'offline'}]")
        if Confirm.ask("Connect a server?", default=False):
            await self._connect_server()

    async def _connect_server(self) -> None:
        name = Prompt.ask("Server name")
        user = self.host.session_manager.current().user
        with self.host.database.session() as session:
            await self.host.server_manager.connect(name, user, AccessRepository(session))
        self.host.audit(AuditEventType.SERVER_CONNECT.value, user.username, True, name)
        await self.host.refresh_discovery()

    async def _tools(self) -> None:
        user = self.host.session_manager.current().user
        self.host.authorization.require_permission(user, PermissionCode.LIST_TOOLS.value)
        self.renderer.tools(self.host.tool_manager.list_tools())

    async def _resources(self) -> None:
        user = self.host.session_manager.current().user
        self.host.authorization.require_permission(user, PermissionCode.LIST_RESOURCES.value)
        self.renderer.resources(self.host.resource_manager.list_resources())

    async def _prompts(self) -> None:
        user = self.host.session_manager.current().user
        self.host.authorization.require_permission(user, PermissionCode.VIEW_PROMPTS.value)
        self.renderer.prompts(self.host.prompt_manager.list_prompts())

    async def _execute_tool(self) -> None:
        qualified_name = Prompt.ask("Tool")
        raw_args = Prompt.ask("Arguments JSON", default="{}")
        arguments = parse_json_object(raw_args)
        user = self.host.session_manager.current().user
        start = perf_counter()
        with self.host.database.session() as session:
            result = await self.host.tool_manager.execute(
                qualified_name,
                arguments,
                user,
                self.host.server_manager.connections,
                AccessRepository(session),
            )
        self.host.audit_duration(
            AuditEventType.TOOL_EXECUTE.value, user.username, True, qualified_name, start
        )
        self.console.print(result)

    async def _administration(self) -> None:
        user = self.host.session_manager.current().user
        self.host.authorization.require_permission(user, PermissionCode.MANAGE_USERS.value)
        with self.host.database.session() as session:
            from app.persistence.repositories import RoleRepository, UserRepository
            users = UserRepository(session).list_users()
            roles = RoleRepository(session).list_roles()
        self.console.print(f"Users: {', '.join(user.username for user in users)}")
        self.console.print(f"Roles: {', '.join(role.name for role in roles)}")

    async def _audit_logs(self) -> None:
        user = self.host.session_manager.current().user
        self.host.authorization.require_permission(user, PermissionCode.VIEW_LOGS.value)
        for item in self.host.audit_logs():
            status = "ok" if item.success else "failed"
            self.console.print(f"{item.timestamp} {item.event_type} {status} {item.username}: {item.details}")

    async def _refresh(self) -> None:
        user = self.host.session_manager.current().user
        self.host.authorization.require_permission(user, PermissionCode.REFRESH_SERVERS.value)
        await self.host.refresh_discovery()
        self.renderer.message("Discovery refreshed.")
