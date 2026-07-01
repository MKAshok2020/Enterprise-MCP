"""FastAPI web entrypoint."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.application.host import Host
from app.domain.exceptions import EnterpriseMCPError
from app.presentation.web.routes import router
from app.presentation.web.routes import templates


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and dispose the enterprise host."""
    host = Host()
    host.initialize()
    app.state.host = host
    try:
        yield
    finally:
        await host.shutdown()


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="Enterprise MCP Host", lifespan=lifespan)
    app.mount(
        "/static",
        StaticFiles(directory="app/presentation/web/static"),
        name="static",
    )
    app.include_router(router)

    @app.exception_handler(EnterpriseMCPError)
    async def enterprise_error(
        request: Request,
        exc: EnterpriseMCPError,
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"title": "Error", "session": None, "error": str(exc)},
            status_code=400,
        )

    return app


app = create_app()
