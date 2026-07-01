"""Domain enumerations."""

from enum import StrEnum

 

class AuditEventType(StrEnum):
    """Auditable enterprise host events."""

    AUTH_FAILURE = "auth.failure"
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    PERMISSION_DENIED = "security.permission_denied"
    SERVER_CONNECT = "server.connect"
    SERVER_DISCONNECT = "server.disconnect"
    SERVER_REFRESH = "server.refresh"
    TOOL_EXECUTE = "tool.execute"
    CONFIG_CHANGE = "config.change"
    ERROR = "system.error"


class PermissionCode(StrEnum):
    """Built-in permission codes."""

    CONNECT_SERVERS = "servers.connect"
    DISCONNECT_SERVERS = "servers.disconnect"
    EXECUTE_TOOLS = "tools.execute"
    MANAGE_USERS = "users.manage"
    MANAGE_ROLES = "roles.manage"
    VIEW_LOGS = "logs.view"
    REFRESH_SERVERS = "servers.refresh"
    CHANGE_CONFIG = "config.change"
    LIST_SERVERS = "servers.list"
    LIST_TOOLS = "tools.list"
    LIST_RESOURCES = "resources.list"
    VIEW_PROMPTS = "prompts.view"


class SessionStatus(StrEnum):
    """Session lifecycle states."""

    ACTIVE = "active"
    EXPIRED = "expired"
    LOGGED_OUT = "logged_out"


class IdentityProviderType(StrEnum):
    """Supported third-party and enterprise identity protocols."""

    OAUTH2 = "oauth2"
    OIDC = "oidc"
    SAML = "saml"


class AuthSource(StrEnum):
    """User authentication source."""

    LOCAL = "local"
    FEDERATED = "federated"
    MIXED = "mixed"



class Protocol(StrEnum):
    HTTP = "http"
    HTTPS = "https"
    REST = "rest"
    GRPC = "grpc"
    SOAP = "soap"
    GRAPHQL = "graphql"
    WEBSOCKET = "websocket"
    STDIO = "stdio"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    MQTT = "mqtt"
    DATABASE = "database"
    FTP = "ftp"
    SFTP = "sftp"
    REDIS = "redis"
    CUSTOM = "custom"



class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class AuthenticationType(StrEnum):
    NONE = "none"
    API_KEY = "apikey"
    BASIC = "basic"
    BEARER = "bearer"
    OAUTH2 = "oauth2"
    CERTIFICATE = "certificate"
    

