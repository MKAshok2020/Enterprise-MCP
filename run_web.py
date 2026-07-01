"""Run the Enterprise MCP Host web application."""

import uvicorn

from app.config.settings import get_settings


def main() -> None:
    """Start the FastAPI server."""
    settings = get_settings()
    uvicorn.run(
        "app.presentation.web.main:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
