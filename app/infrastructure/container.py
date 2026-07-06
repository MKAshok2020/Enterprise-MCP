from dependency_injector import containers, providers

from app.application.host import Host
from app.config.settings import get_settings
from app.infrastructure.configuration import ConfigurationLoader
from app.persistence.database import Database
from app.security.auth_service import AuthenticationService
from app.security.authorization_service import AuthorizationService
from app.security.jwt_service import JWTService
from app.security.password_service import PasswordService
from app.security.session_store import SessionStore
from app.security.sso_service import SSOService
from app.application.chat_manager import ChatManager
from app.application.document_store import DocumentStore
from app.application.prompt_manager import PromptManager
from app.application.resource_manager import ResourceManager
from app.application.session_manager import SessionManager
from app.application.tool_manager import ToolManager
from app.services.factory.service_container import ServiceContainer


class AppContainer(containers.DeclarativeContainer):
    """Dependency injection container for the Enterprise MCP Host."""

    settings = providers.Singleton(get_settings)
    database = providers.Singleton(Database, settings)
    passwords = providers.Singleton(PasswordService)
    jwt = providers.Singleton(JWTService, settings)
    sessions = providers.Singleton(SessionStore, settings)
    auth = providers.Singleton(AuthenticationService, passwords, jwt, sessions)
    sso = providers.Singleton(SSOService)
    authorization = providers.Singleton(AuthorizationService)
    session_manager = providers.Singleton(SessionManager, sessions)
    loader = providers.Singleton(ConfigurationLoader, settings)
    service_factory = ServiceContainer.service_factory
    document_store = providers.Singleton(DocumentStore, settings)
    tool_manager = providers.Singleton(ToolManager, authorization)
    chat_manager = providers.Singleton(
        ChatManager,
        tool_manager,
        document_store,
        settings.provided.llm_model_name,
        settings.provided.ollama_base_url,
    )
    resource_manager = providers.Singleton(ResourceManager)
    prompt_manager = providers.Singleton(PromptManager)

    host = providers.Singleton(
        Host,
        settings=settings,
        database=database,
        passwords=passwords,
        jwt=jwt,
        sessions=sessions,
        auth=auth,
        sso=sso,
        authorization=authorization,
        session_manager=session_manager,
        loader=loader,
        service_factory=service_factory,
        tool_manager=tool_manager,
        document_store=document_store,
        chat_manager=chat_manager,
        resource_manager=resource_manager,
        prompt_manager=prompt_manager,
    )
