"""Server connection manager."""

from app.domain.enums import PermissionCode
from app.domain.models import ServerDefinition, User
from app.infrastructure.mcp_client import MCPServerConnection
from app.persistence.repositories import AccessRepository
from app.security.authorization_service import AuthorizationService


class ServerManager:
    """Connects, disconnects, and tracks MCP servers."""

    def __init__(
        self,
        servers: list[ServerDefinition],
        authorization: AuthorizationService,
    ) -> None:
        self.servers = {server.name: server for server in servers}
        self.authorization = authorization
        self.connections: dict[str, MCPServerConnection] = {}

    def list_servers(self) -> list[ServerDefinition]:
        """Return configured servers."""
        return list(self.servers.values())

    def connected_names(self) -> list[str]:
        """Return connected server names."""
        return sorted(self.connections)

    async def connect(
        self,
        server_name: str,
        user: User,
        access_repository: AccessRepository,
    ) -> None:
        """Connect to a server after authorization."""
        server = self.servers[server_name]
        self.authorization.require_permission(user, PermissionCode.CONNECT_SERVERS.value)
        self.authorization.require_server_access(user, server, access_repository)
        connection = MCPServerConnection(server)
        await connection.connect()
        self.connections[server_name] = connection

    async def disconnect(self, server_name: str, user: User) -> None:
        """Disconnect from a server after authorization."""
        self.authorization.require_permission(user, PermissionCode.DISCONNECT_SERVERS.value)
        connection = self.connections.pop(server_name, None)
        if connection is not None:
            await connection.close()

    async def shutdown(self) -> None:
        """Disconnect all active servers."""
        for connection in list(self.connections.values()):
            await connection.close()
        self.connections.clear()

