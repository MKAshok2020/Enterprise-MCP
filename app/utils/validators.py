"""Input validators."""

import json
from typing import Any

from app.domain.exceptions import ConfigurationError


def parse_json_object(value: str) -> dict[str, Any]:
    """Parse a CLI JSON object value."""
    if not value.strip():
        return {}
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ConfigurationError("Tool arguments must be a JSON object.")
    return data


def require_choice(value: str, choices: set[str]) -> str:
    """Validate a menu choice."""
    if value not in choices:
        raise ValueError(f"Choose one of: {', '.join(sorted(choices))}")
    return value

