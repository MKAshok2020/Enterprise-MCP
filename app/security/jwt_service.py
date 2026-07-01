"""JWT issue, refresh, and validation service."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt

from app.config.settings import Settings
from app.domain.exceptions import AuthenticationFailedError, SessionExpiredError
from app.domain.models import AuthTokens, User


class JWTService:
    """JWT access and refresh token service."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def issue_tokens(self, user: User) -> AuthTokens:
        """Issue access and refresh tokens for a user."""
        now = datetime.now(timezone.utc)
        access_expiry = now + timedelta(minutes=self.settings.access_token_minutes)
        refresh_expiry = now + timedelta(minutes=self.settings.refresh_token_minutes)
        access = self._encode(user, "access", access_expiry)
        refresh = self._encode(user, "refresh", refresh_expiry)
        return AuthTokens(access, refresh, access_expiry)

    def refresh(self, refresh_token: str, user: User) -> AuthTokens:
        """Validate a refresh token and issue a new token pair."""
        payload = self.decode(refresh_token)
        if payload.get("type") != "refresh" or payload.get("sub") != user.username:
            raise AuthenticationFailedError("Invalid refresh token.")
        return self.issue_tokens(user)

    def decode(self, token: str) -> dict[str, object]:
        """Decode and validate a JWT."""
        try:
            return jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.settings.jwt_algorithm],
            )
        except jwt.ExpiredSignatureError as exc:
            raise SessionExpiredError("JWT expired.") from exc
        except jwt.PyJWTError as exc:
            raise AuthenticationFailedError("Invalid JWT.") from exc

    def _encode(self, user: User, token_type: str, expires_at: datetime) -> str:
        payload = {
            "sub": user.username,
            "uid": user.id,
            "roles": sorted(user.role_names),
            "type": token_type,
            "jti": str(uuid4()),
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, self.settings.jwt_secret, self.settings.jwt_algorithm)

