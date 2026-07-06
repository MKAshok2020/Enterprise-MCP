"""Prompt discovery manager."""

import logging
from typing import Any

from app.domain.models import PromptDefinition

logger = logging.getLogger("enterprise_mcp_host")


class PromptManager:
    """Discovers MCP prompts."""

    def __init__(self) -> None:
        self._prompts: list[PromptDefinition] = []

    async def refresh(self, connections: dict[str, Any]) -> list[PromptDefinition]:
        """Refresh prompts from connected servers."""
        logger.info("Refreshing prompts from %d connections.", len(connections))
        self._prompts.clear()
        for connection in connections.values():
            self._prompts.extend(await connection.list_prompts())
        prompts = self.list_prompts()
        logger.info("Discovered %d prompts.", len(prompts))
        return prompts

    def list_prompts(self) -> list[PromptDefinition]:
        """Return discovered prompts."""
        return list(self._prompts)

