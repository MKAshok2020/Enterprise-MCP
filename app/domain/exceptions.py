"""Domain exceptions used across layers."""


class EnterpriseMCPError(Exception):
    """Base application error."""


class AuthenticationFailedError(EnterpriseMCPError):
    """Raised when credentials or tokens are invalid."""


class AuthorizationError(EnterpriseMCPError):
    """Raised when the current user lacks permission."""


class SessionExpiredError(AuthenticationFailedError):
    """Raised when a session is no longer active."""


class ConfigurationError(EnterpriseMCPError):
    """Raised for invalid application or server configuration."""


class ServerUnavailableError(EnterpriseMCPError):
    """Raised when an MCP server cannot be reached."""


class ToolExecutionError(EnterpriseMCPError):
    """Raised when a tool call fails."""

