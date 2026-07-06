"""Application session manager."""

import logging

from app.domain.models import UserSession
from app.security.session_store import SessionStore

logger = logging.getLogger("enterprise_mcp_host")


class SessionManager:
    """Maintains current CLI session context."""

    def __init__(self, session_store: SessionStore) -> None:
        self.session_store = session_store
        self.current_session_id: str | None = None

    def set_current(self, session: UserSession) -> None:
        """Set current session."""
        self.current_session_id = session.session_id
        logger.info("Set current session %s.", session.session_id)

    def current(self) -> UserSession:
        """Return current active session."""
        if self.current_session_id is None:
            logger.error("No active session when requesting current session.")
            raise RuntimeError("No active session.")
        session = self.session_store.get(self.current_session_id)
        logger.info("Retrieved current session %s.", session.session_id)
        return session

    def clear(self) -> None:
        """Clear current session."""
        logger.info("Clearing current session %s.", self.current_session_id)
        self.current_session_id = None

