"""CLI screens."""

from getpass import getpass

from rich.console import Console
from rich.prompt import Prompt


class LoginScreen:
    """Login input screen."""

    def __init__(self, console: Console) -> None:
        self.console = console

    def collect_credentials(self) -> tuple[str, str]:
        """Collect username and password."""
        self.console.print("=" * 36)
        self.console.print("[bold cyan]Enterprise MCP Host[/]")
        self.console.print("Local login enabled. SSO providers are configured for callback integration.")
        self.console.print("=" * 36)
        username = Prompt.ask("Username")
        password = getpass("Password: ")
        self.console.print("=" * 36)
        return username, password


class MenuScreen:
    """Main menu screen."""

    def __init__(self, console: Console) -> None:
        self.console = console

    def choice(self) -> str:
        """Render menu and collect a choice."""
        self.console.print()
        self.console.print("[bold cyan]Enterprise MCP Host[/]")
        self.console.print("1. Connected Servers")
        self.console.print("2. List Tools")
        self.console.print("3. List Resources")
        self.console.print("4. List Prompts")
        self.console.print("5. Execute Tool")
        self.console.print("6. Administration")
        self.console.print("7. Audit Logs")
        self.console.print("8. Refresh Servers")
        self.console.print("9. Logout")
        self.console.print("0. Exit")
        return Prompt.ask("Choice", choices=[str(i) for i in range(10)])
