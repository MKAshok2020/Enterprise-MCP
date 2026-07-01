"""Resource discovery manager."""

from typing import Any

from app.domain.models import ResourceDefinition


class ResourceManager:
    """Discovers MCP resources."""

    def __init__(self) -> None:
        self._resources: list[ResourceDefinition] = []

    async def refresh(self, connections: dict[str, Any]) -> list[ResourceDefinition]:
        """Refresh resources from connected servers."""
        self._resources.clear()
        for connection in connections.values():
            self._resources.extend(await connection.list_resources())
        return self.list_resources()

    def list_resources(self) -> list[ResourceDefinition]:
        """Return discovered resources."""
        return list(self._resources)

