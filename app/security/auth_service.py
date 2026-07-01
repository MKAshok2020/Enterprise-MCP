"""Authentication service."""

from datetime import datetime, timezone
from uuid import uuid4

from app.domain.enums import AuthSource
from app.domain.exceptions import AuthenticationFailedError
from app.domain.models import FederatedIdentityProfile, User, UserSession
from app.persistence.repositories import IdentityRepository, UserRepository, to_domain_user
from app.security.jwt_service import JWTService
from app.security.password_service import PasswordService
from app.security.session_store import SessionStore


class AuthenticationService:
    """Coordinates username/password and token authentication."""

    def __init__(
        self,
        password_service: PasswordService,
        jwt_service: JWTService,
        session_store: SessionStore,
    ) -> None:
        self.password_service = password_service
        self.jwt_service = jwt_service
        self.session_store = session_store

    def login(self, username: str, password: str, users: UserRepository) -> UserSession:
        """Authenticate a user and create a session."""
        entity = users.find_by_username(username)
        if entity is None or not entity.is_active:
            raise AuthenticationFailedError("Authentication failed.")
        if entity.password_hash is None:
            raise AuthenticationFailedError("Use federated SSO for this account.")
        if not self.password_service.verify_password(password, entity.password_hash):
            raise AuthenticationFailedError("Authentication failed.")
        users.mark_login(entity)
        user = to_domain_user(entity)
        return self._create_session(user)

    def login_federated(
        self,
        profile: FederatedIdentityProfile,
        users: UserRepository,
        identities: IdentityRepository,
    ) -> UserSession:
        """Authenticate or provision a user from a verified external identity."""
        provider = identities.get_provider(profile.provider_name)
        if provider is None or not provider.is_active:
            raise AuthenticationFailedError("Identity provider is not enabled.")
        linked_identity = identities.find_identity(provider.name, profile.subject)
        if linked_identity is not None:
            users.mark_login(linked_identity.user)
            user = to_domain_user(linked_identity.user)
            return self._create_session(user)
        entity = users.find_by_email(profile.email)
        if entity is None:
            entity = users.create_user(
                username=self._username_from_profile(profile),
                password_hash=None,
                email=profile.email,
                display_name=profile.display_name,
                auth_source=AuthSource.FEDERATED.value,
            )
            users.assign_role(entity, provider.default_role)
        elif entity.auth_source == AuthSource.LOCAL.value:
            entity.auth_source = AuthSource.MIXED.value
        identities.link_identity(entity, provider, profile)
        users.mark_login(entity)
        return self._create_session(to_domain_user(entity))

    def _create_session(self, user: User) -> UserSession:
        """Create and remember an authenticated session."""
        tokens = self.jwt_service.issue_tokens(user)
        now = datetime.now(timezone.utc)
        session = UserSession(str(uuid4()), user, tokens, now, now)
        self.session_store.save(session)
        return session

    def _username_from_profile(self, profile: FederatedIdentityProfile) -> str:
        local_part = profile.email.split("@", maxsplit=1)[0]
        provider_part = profile.provider_name.replace(" ", "-").lower()
        return f"{provider_part}-{local_part}".lower()

    def refresh(self, session: UserSession) -> UserSession:
        """Refresh session tokens."""
        session.tokens = self.jwt_service.refresh(session.tokens.refresh_token, session.user)
        session.touch()
        self.session_store.save(session)
        return session

    def logout(self, session_id: str) -> None:
        """Terminate an active session."""
        self.session_store.remove(session_id)
