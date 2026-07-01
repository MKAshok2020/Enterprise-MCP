"""Database engine and initialization."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import Settings
from app.domain.exceptions import ConfigurationError
from app.persistence.entities import Base


class Database:
    """Owns SQLAlchemy engine and session factory."""

    def __init__(self, settings: Settings) -> None:
        self.engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False, future=True
        )

    def create_schema(self) -> None:
        """Create database tables."""
        try:
            Base.metadata.create_all(self.engine)
        except SQLAlchemyError as exc:
            raise ConfigurationError(self._connection_error_message(exc)) from exc

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Provide a transactional session."""
        db_session = self.session_factory()
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise
        finally:
            db_session.close()

    def _connection_error_message(self, exc: SQLAlchemyError) -> str:
        safe_url = make_url(str(self.engine.url)).render_as_string(hide_password=True)
        return (
            "Database connection failed. Verify MCP_HOST_DATABASE_URL, create the "
            "MySQL database/user, and confirm the password is correct. "
            f"Current URL: {safe_url}. Details: {exc.__class__.__name__}: {exc}"
        )
