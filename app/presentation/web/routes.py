"""FastAPI routes for the Enterprise MCP Host web app."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.domain.enums import AuditEventType, PermissionCode
from app.domain.exceptions import AuthenticationFailedError, EnterpriseMCPError
from app.persistence.repositories import AccessRepository
from app.presentation.web.dependencies import current_session, get_host
from app.utils.validators import parse_json_object


templates = Jinja2Templates(directory="app/presentation/web/templates")
router = APIRouter()


def redirect(path: str) -> RedirectResponse:
    """Return a 303 redirect."""
    return RedirectResponse(path, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> RedirectResponse:
    """Redirect the root to dashboard or login."""
    host = get_host(request)
    session_id = request.cookies.get(host.settings.web_session_cookie_name)
    return redirect("/dashboard" if session_id else "/login")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, expired: int = 0) -> HTMLResponse:
    """Render login page."""
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": None, "expired": bool(expired), "title": "Login"},
    )


@router.post("/login", response_model=None)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Authenticate and create a browser session cookie."""
    host = get_host(request)
    try:
        session = host.login(username, password)
    except AuthenticationFailedError as exc:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": str(exc),
                "expired": False,
                "title": "Login",
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = redirect("/dashboard")
    response.set_cookie(
        host.settings.web_session_cookie_name,
        session.session_id,
        httponly=True,
        secure=host.settings.web_session_cookie_secure,
        samesite="lax",
    )

    return response



# @router.post("/login")
# async def login(
#     request: Request,
#     username: str = Form(...),
#     password: str = Form(...),
# ) -> HTMLResponse | RedirectResponse:
#     """Authenticate and create a browser session cookie."""
#     host = get_host(request)
#     try:
#         session = host.login(username, password)
#     except AuthenticationFailedError as exc:
#         return templates.TemplateResponse(
#             request,
#             "login.html",
#             {"error": str(exc), "expired": False, "title": "Login"},
#             status_code=status.HTTP_401_UNAUTHORIZED,
#         )
#     response = redirect("/dashboard")
#     response.set_cookie(
#         host.settings.web_session_cookie_name,
#         session.session_id,
#         httponly=True,
#         secure=host.settings.web_session_cookie_secure,
#         samesite="lax",
#     )
#     return response


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Logout the current browser session."""
    host = get_host(request)
    session = current_session(request, host)
    host.auth.logout(session.session_id)
    host.audit(AuditEventType.LOGOUT.value, session.user.username, True, "Web logout")
    response = redirect("/login")
    response.delete_cookie(host.settings.web_session_cookie_name)
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render operator dashboard."""
    host = get_host(request)
    session = current_session(request, host)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "title": "Dashboard",
            "session": session,
            "connected_servers": host.server_manager.connected_names(),
            "servers": host.server_manager.list_servers(),
            "tools": host.tool_manager.list_tools(),
            "resources": host.resource_manager.list_resources(),
            "prompts": host.prompt_manager.list_prompts(),
        },
    )


@router.post("/servers/connect")
async def connect_server(request: Request, server_name: str = Form(...)) -> RedirectResponse:
    """Connect to an MCP server."""
    host = get_host(request)
    session = current_session(request, host)
    try:
        with host.database.session() as db_session:
            await host.server_manager.connect(
                server_name, session.user, AccessRepository(db_session)
            )
        host.audit(AuditEventType.SERVER_CONNECT.value, session.user.username, True, server_name)
        await host.refresh_discovery(session.user)
    except EnterpriseMCPError as exc:
        host.audit(AuditEventType.ERROR.value, session.user.username, False, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return redirect("/dashboard")


@router.post("/servers/refresh")
async def refresh_servers(request: Request) -> RedirectResponse:
    """Refresh discovered MCP tools, resources, and prompts."""
    host = get_host(request)
    session = current_session(request, host)
    host.authorization.require_permission(session.user, PermissionCode.REFRESH_SERVERS.value)
    await host.refresh_discovery(session.user)
    return redirect("/dashboard")


@router.get("/tools", response_class=HTMLResponse)
async def tools(request: Request) -> HTMLResponse:
    """Render discovered tools."""
    host = get_host(request)
    session = current_session(request, host)
    host.authorization.require_permission(session.user, PermissionCode.LIST_TOOLS.value)
    return templates.TemplateResponse(
        request,
        "tools.html",
        {"title": "Tools", "session": session, "tools": host.tool_manager.list_tools()},
    )


@router.post("/tools/execute", response_class=HTMLResponse)
async def execute_tool(
    request: Request,
    qualified_name: str = Form(...),
    arguments_json: str = Form("{}"),
) -> HTMLResponse:
    """Execute an authorized MCP tool."""
    host = get_host(request)
    session = current_session(request, host)
    start = perf_counter()
    arguments = parse_json_object(arguments_json)
    try:
        result = await _execute_tool(host, session.user, qualified_name, arguments)
        host.audit_duration(
            AuditEventType.TOOL_EXECUTE.value,
            session.user.username,
            True,
            qualified_name,
            start,
        )
    except EnterpriseMCPError as exc:
        host.audit(AuditEventType.ERROR.value, session.user.username, False, str(exc))
        result = {"error": str(exc)}
    return templates.TemplateResponse(
        request,
        "tool_result.html",
        {"title": "Tool Result", "session": session, "result": result},
    )


@router.get("/resources", response_class=HTMLResponse)
async def resources(request: Request) -> HTMLResponse:
    """Render discovered resources."""
    host = get_host(request)
    session = current_session(request, host)
    host.authorization.require_permission(session.user, PermissionCode.LIST_RESOURCES.value)
    return templates.TemplateResponse(
        request,
        "resources.html",
        {"title": "Resources", "session": session, "resources": host.resource_manager.list_resources()},
    )


@router.get("/prompts", response_class=HTMLResponse)
async def prompts(request: Request) -> HTMLResponse:
    """Render discovered prompts."""
    host = get_host(request)
    session = current_session(request, host)
    host.authorization.require_permission(session.user, PermissionCode.VIEW_PROMPTS.value)
    return templates.TemplateResponse(
        request,
        "prompts.html",
        {"title": "Prompts", "session": session, "prompts": host.prompt_manager.list_prompts()},
    )


@router.get("/audit-logs", response_class=HTMLResponse)
async def audit_logs(request: Request) -> HTMLResponse:
    """Render audit logs."""
    host = get_host(request)
    session = current_session(request, host)
    host.authorization.require_permission(session.user, PermissionCode.VIEW_LOGS.value)
    return templates.TemplateResponse(
        request,
        "audit_logs.html",
        {"title": "Audit Logs", "session": session, "logs": host.audit_logs()},
    )


async def _execute_tool(
    host: Any,
    user: Any,
    qualified_name: str,
    arguments: dict[str, Any],
) -> Any:
    with host.database.session() as db_session:
        return await host.tool_manager.execute(
            qualified_name,
            arguments,
            user,
            host.server_manager.connections,
            AccessRepository(db_session),
        )
