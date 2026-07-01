"""SSO login flow helpers for OAuth2, OIDC, and SAML providers."""

from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from urllib.parse import urlencode

from app.domain.exceptions import AuthenticationFailedError, ConfigurationError
from app.persistence.entities import IdentityProviderEntity
from app.persistence.repositories import IdentityRepository


class SSOService:
    """Creates provider login requests and tracks SSO handshakes."""

    def begin_login(
        self,
        provider_name: str,
        redirect_uri: str,
        identities: IdentityRepository,
    ) -> str:
        """Create an SSO login session and return the provider login URL."""
        provider = identities.get_provider(provider_name)
        if provider is None or not provider.is_active:
            raise AuthenticationFailedError("Identity provider is not enabled.")
        state = token_urlsafe(32)
        nonce = token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        identities.create_sso_session(provider, state, redirect_uri, expires_at, nonce)
        if provider.provider_type == "saml":
            return self._saml_url(provider, state)
        return self._oauth_url(provider, redirect_uri, state, nonce)

    def _oauth_url(
        self,
        provider: IdentityProviderEntity,
        redirect_uri: str,
        state: str,
        nonce: str,
    ) -> str:
        if provider.authorization_url is None:
            raise ConfigurationError("Provider authorization URL is required.")
        params = {
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": provider.scopes,
            "state": state,
            "nonce": nonce,
        }
        return f"{provider.authorization_url}?{urlencode(params)}"

    def _saml_url(self, provider: IdentityProviderEntity, state: str) -> str:
        if provider.authorization_url is None:
            raise ConfigurationError("SAML login URL is required.")
        params = {"RelayState": state, "sp_entity_id": provider.client_id}
        return f"{provider.authorization_url}?{urlencode(params)}"
