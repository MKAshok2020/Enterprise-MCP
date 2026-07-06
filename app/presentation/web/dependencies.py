"""Web dependency helpers."""

from collections.abc import AsyncIterator

from fastapi import HTTPException, Request, status

from app.application.host import Host
from app.domain.exceptions import SessionExpiredError
from app.domain.models import UserSession
from app.infrastructure.container import AppContainer


async def lifespan_host() -> AsyncIterator[Host]:
    """Create and initialize the host for the FastAPI lifespan."""
    container = AppContainer()
    host = container.host()
    host.initialize()
    try:
        yield host
    finally:
        await host.shutdown()


def get_host(request: Request) -> Host:
    """Return the application host from app state."""
    return request.app.state.host


def current_session(request: Request, host: Host) -> UserSession:
    """Return the authenticated web session."""
    cookie_name = host.settings.web_session_cookie_name
    session_id = request.cookies.get(cookie_name)
    if not session_id:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    try:
        return host.sessions.get(session_id)
    except SessionExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login?expired=1"},
        ) from exc

