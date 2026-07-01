"""CLI entrypoint."""

import asyncio

from rich.console import Console

from app.application.host import Host
from app.domain.exceptions import AuthenticationFailedError, EnterpriseMCPError
from app.presentation.menu import MenuController
from app.presentation.screens import LoginScreen


async def async_main() -> None:
    """Run the Enterprise MCP Host CLI."""
    console = Console()
    host: Host | None = None
    try:
        host = Host()
        host.initialize()
        login = LoginScreen(console)
        keep_running = True
        while keep_running:
            username, password = login.collect_credentials()
            try:
                host.login(username, password)
            except AuthenticationFailedError as exc:
                console.print(f"[red]{exc}[/]")
                continue
            keep_running = await MenuController(host, console).run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Graceful shutdown requested.[/]")
    except EnterpriseMCPError as exc:
        console.print(f"[red]{exc}[/]")
    finally:
        if host is not None:
            await host.shutdown()


def main() -> None:
    """Start the CLI application."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
