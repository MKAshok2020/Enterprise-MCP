"""Resource discovery manager."""

import logging
from typing import Any

from app.domain.models import ResourceDefinition

logger = logging.getLogger("enterprise_mcp_host")


class ResourceManager:
    """Discovers MCP resources."""

    def __init__(self) -> None:
        self._resources: list[ResourceDefinition] = []

    async def refresh(self, connections: dict[str, Any]) -> list[ResourceDefinition]:
        """Refresh resources from connected servers."""
        logger.info("Refreshing resources from %d connections.", len(connections))
        self._resources.clear()
        for connection in connections.values():
            self._resources.extend(await connection.list_resources())
        resources = self.list_resources()
        logger.info("Discovered %d resources.", len(resources))
        return resources

    def list_resources(self) -> list[ResourceDefinition]:
        """Return discovered resources."""
        return list(self._resources)

