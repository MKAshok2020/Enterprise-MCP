"""In-memory active session store."""

from datetime import datetime, timedelta, timezone

from app.config.settings import Settings
from app.domain.exceptions import SessionExpiredError
from app.domain.models import UserSession


class SessionStore:
    """Keeps active sessions for the CLI process."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sessions: dict[str, UserSession] = {}

    def save(self, session: UserSession) -> None:
        """Remember an active session."""
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> UserSession:
        """Return an active session or raise if expired."""
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionExpiredError("Session not found.")
        if self.is_expired(session):
            self._sessions.pop(session_id, None)
            raise SessionExpiredError("Session expired.")
        session.touch()
        return session

    def remove(self, session_id: str) -> None:
        """Remove a session."""
        self._sessions.pop(session_id, None)

    def is_expired(self, session: UserSession) -> bool:
        """Return whether a session exceeded timeout."""
        timeout = timedelta(minutes=self.settings.session_timeout_minutes)
        return datetime.now(timezone.utc) - session.last_seen_at > timeout

