"""Run the Enterprise MCP Host web application."""

import uvicorn
import os

from app.config.settings import get_settings


debug = os.getenv("DEBUG", "false").lower() == "true"
def main() -> None:
    """Start the FastAPI server."""
    settings = get_settings()
    uvicorn.run(
        "app.presentation.web.main:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=not debug,
    )


if __name__ == "__main__":
    main()
