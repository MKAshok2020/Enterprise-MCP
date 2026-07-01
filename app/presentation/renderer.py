"""Rich rendering helpers."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.domain.models import PromptDefinition, ResourceDefinition, ToolDefinition
from app.utils.helpers import truncate


class Renderer:
    """Renders CLI views."""

    def __init__(self, console: Console) -> None:
        self.console = console

    def header(self, title: str) -> None:
        """Render a screen header."""
        self.console.print(Panel.fit(title, style="bold cyan"))

    def status(self, username: str, roles: set[str], servers: list[str], tools: int) -> None:
        """Render current user status."""
        role_text = ", ".join(sorted(roles))
        server_text = ", ".join(servers) if servers else "None"
        self.console.print(f"[bold]Current User:[/] {username}")
        self.console.print(f"[bold]Current Role:[/] {role_text}")
        self.console.print(f"[bold]Connected Servers:[/] {server_text}")
        self.console.print(f"[bold]Available Tools:[/] {tools}")

    def tools(self, tools: list[ToolDefinition]) -> None:
        """Render tools table."""
        table = Table(title="Available Tools")
        table.add_column("Qualified Name")
        table.add_column("Description")
        table.add_column("Schema")
        for tool in tools:
            table.add_row(tool.qualified_name, truncate(tool.description), str(tool.input_schema))
        self.console.print(table)

    def resources(self, resources: list[ResourceDefinition]) -> None:
        """Render resources table."""
        table = Table(title="Resources")
        table.add_column("Server")
        table.add_column("URI")
        table.add_column("Name")
        table.add_column("MIME")
        for item in resources:
            table.add_row(item.server_name, item.uri, item.name, item.mime_type or "")
        self.console.print(table)

    def prompts(self, prompts: list[PromptDefinition]) -> None:
        """Render prompts table."""
        table = Table(title="Prompts")
        table.add_column("Server")
        table.add_column("Name")
        table.add_column("Description")
        for item in prompts:
            table.add_row(item.server_name, item.name, truncate(item.description))
        self.console.print(table)

    def message(self, message: str, style: str = "green") -> None:
        """Render a message."""
        self.console.print(f"[{style}]{message}[/]")

