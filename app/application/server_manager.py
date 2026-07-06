"""Server connection manager."""

import logging

from app.domain.enums import PermissionCode
from app.domain.models import ServerDefinition, User
from app.infrastructure.mcp_client import MCPServerConnection
from app.persistence.repositories import AccessRepository
from app.services.factory.service_factory import ServiceFactory
from app.security.authorization_service import AuthorizationService

logger = logging.getLogger("enterprise_mcp_host")


class ServerManager:
    """Connects, disconnects, and tracks MCP servers."""

    def __init__(
        self,
        servers: list[ServerDefinition],
        authorization: AuthorizationService,
        service_factory: ServiceFactory | None = None,
    ) -> None:
        self.servers = {server.name: server for server in servers}
        self.authorization = authorization
        self.service_factory = service_factory
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
        logger.info("User %s connecting to server %s.", user.username, server_name)
        server = self.servers[server_name]
        self.authorization.require_permission(user, PermissionCode.CONNECT_SERVERS.value)
        self.authorization.require_server_access(user, server, access_repository)
        connection = MCPServerConnection(server, self.service_factory)
        await connection.connect()
        self.connections[server_name] = connection
        logger.info("Connected to server %s.", server_name)

    async def disconnect(self, server_name: str, user: User) -> None:
        """Disconnect from a server after authorization."""
        logger.info("User %s disconnecting from server %s.", user.username, server_name)
        self.authorization.require_permission(user, PermissionCode.DISCONNECT_SERVERS.value)
        connection = self.connections.pop(server_name, None)
        if connection is not None:
            await connection.close()
            logger.info("Disconnected from server %s.", server_name)
        else:
            logger.warning("Disconnect called for unknown server %s.", server_name)

    async def shutdown(self) -> None:
        """Disconnect all active servers."""
        logger.info("Shutting down %d server connections.", len(self.connections))
        for connection in list(self.connections.values()):
            await connection.close()
        self.connections.clear()

