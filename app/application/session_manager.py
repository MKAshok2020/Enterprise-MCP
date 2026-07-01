"""Application session manager."""

from app.domain.models import UserSession
from app.security.session_store import SessionStore


class SessionManager:
    """Maintains current CLI session context."""

    def __init__(self, session_store: SessionStore) -> None:
        self.session_store = session_store
        self.current_session_id: str | None = None

    def set_current(self, session: UserSession) -> None:
        """Set current session."""
        self.current_session_id = session.session_id

    def current(self) -> UserSession:
        """Return current active session."""
        if self.current_session_id is None:
            raise RuntimeError("No active session.")
        return self.session_store.get(self.current_session_id)

    def clear(self) -> None:
        """Clear current session."""
        self.current_session_id = None

