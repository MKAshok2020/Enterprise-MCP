"""Application settings loaded from JSON and environment."""

import json
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]
APP_SETTINGS_PATH = ROOT_DIR / "app" / "config" / "appsettings.json"
load_dotenv(ROOT_DIR / ".env")


def load_json_defaults() -> dict[str, object]:
    """Load application defaults from JSON configuration."""
    if not APP_SETTINGS_PATH.exists():
        return {}
    with APP_SETTINGS_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {
        "app_name": data.get("app_name"),
        "database_url": data.get("database", {}).get("url"),
        "jwt_secret": data.get("security", {}).get("jwt_secret"),
        "jwt_algorithm": data.get("security", {}).get("jwt_algorithm"),
        "access_token_minutes": data.get("security", {}).get("access_token_minutes"),
        "refresh_token_minutes": data.get("security", {}).get("refresh_token_minutes"),
        "session_timeout_minutes": data.get("security", {}).get("session_timeout_minutes"),
        "mcp_tool_timeout_seconds": data.get("mcp", {}).get("tool_timeout_seconds"),
        "web_host": data.get("web", {}).get("host"),
        "web_port": data.get("web", {}).get("port"),
        "web_session_cookie_name": data.get("web", {}).get("session_cookie_name"),
        "web_session_cookie_secure": data.get("web", {}).get("session_cookie_secure"),
        "audit_ip_placeholder": data.get("audit", {}).get("ip_placeholder"),
    }


JSON_DEFAULTS = {
    key: value for key, value in load_json_defaults().items() if value is not None
}


class Settings(BaseSettings):
    """Typed configuration values."""

    model_config = SettingsConfigDict(env_prefix="MCP_HOST_", extra="ignore")

    app_name: str = str(JSON_DEFAULTS.get("app_name", "Enterprise MCP Host"))
    database_url: str = str(JSON_DEFAULTS.get("database_url", ""))
    jwt_secret: str = str(
        JSON_DEFAULTS.get("jwt_secret", "change-this-secret-in-production")
    )
    jwt_algorithm: str = str(JSON_DEFAULTS.get("jwt_algorithm", "HS256"))
    access_token_minutes: int = int(JSON_DEFAULTS.get("access_token_minutes", 30))
    refresh_token_minutes: int = int(JSON_DEFAULTS.get("refresh_token_minutes", 480))
    session_timeout_minutes: int = int(JSON_DEFAULTS.get("session_timeout_minutes", 30))
    servers_config_path: Path = ROOT_DIR / "app" / "config" / "servers.json"
    knowledge_base_dir: Path = ROOT_DIR / "data" / "knowledge_base"
    llm_model_name: str = "llama3-groq-tool-use:latest"
    embedding_model_name: str = "nomic-embed-text:latest"
    log_file: Path = ROOT_DIR / "logs" / "enterprise_mcp_host.log"
    mcp_tool_timeout_seconds: int = int(JSON_DEFAULTS.get("mcp_tool_timeout_seconds", 60))
    web_host: str = str(JSON_DEFAULTS.get("web_host", "127.0.0.1"))
    web_port: int = int(JSON_DEFAULTS.get("web_port", 8000))
    web_session_cookie_name: str = str(
        JSON_DEFAULTS.get("web_session_cookie_name", "enterprise_mcp_session")
    )
    web_session_cookie_secure: bool = bool(
        JSON_DEFAULTS.get("web_session_cookie_secure", False)
    )
    audit_ip_placeholder: str = str(JSON_DEFAULTS.get("audit_ip_placeholder", "0.0.0.0"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings."""
    return Settings()
