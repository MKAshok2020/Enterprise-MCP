"""FastAPI web entrypoint."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.exception_handlers import http_exception_handler as fastapi_http_exception_handler
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.domain.exceptions import EnterpriseMCPError
from app.infrastructure.container import AppContainer
from app.presentation.web.routes import router
from app.presentation.web.routes import templates


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and dispose the enterprise host."""
    container = AppContainer()
    host = container.host()
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

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if 500 <= exc.status_code < 600:
            return RedirectResponse("/login")
        return await fastapi_http_exception_handler(request, exc)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return RedirectResponse("/login")

    return app


app = create_app()
