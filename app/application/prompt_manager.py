"""Prompt discovery manager."""

from typing import Any

from app.domain.models import PromptDefinition


class PromptManager:
    """Discovers MCP prompts."""

    def __init__(self) -> None:
        self._prompts: list[PromptDefinition] = []

    async def refresh(self, connections: dict[str, Any]) -> list[PromptDefinition]:
        """Refresh prompts from connected servers."""
        self._prompts.clear()
        for connection in connections.values():
            self._prompts.extend(await connection.list_prompts())
        return self.list_prompts()

    def list_prompts(self) -> list[PromptDefinition]:
        """Return discovered prompts."""
        return list(self._prompts)

