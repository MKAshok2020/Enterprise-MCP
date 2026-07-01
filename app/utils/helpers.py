"""General helper functions."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


def truncate(value: str, limit: int = 80) -> str:
    """Truncate text for table display."""
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."

