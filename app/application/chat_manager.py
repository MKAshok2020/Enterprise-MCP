"""Tool-aware chat orchestration for the web host."""

from __future__ import annotations

import re
from typing import Any

from app.domain.models import User
from app.persistence.repositories import AccessRepository
from app.application.tool_manager import ToolManager


class ChatManager:
    """Routes natural language chat messages to available MCP tools."""

    WEATHER_TERMS = {
        "weather",
        "climate",
        "temperature",
        "rain",
        "raining",
        "umbrella",
        "wind",
        "humidity",
        "forecast",
        "cloud",
        "cloudy",
        "sunny",
    }

    LOCATION_PATTERNS = (
        re.compile(r"\b(?:in|at|for|near|around)\s+([A-Za-z][A-Za-z\s,.-]{1,60})", re.I),
        re.compile(r"\bweather\s+([A-Za-z][A-Za-z\s,.-]{1,60})", re.I),
    )

    def __init__(self, tool_manager: ToolManager) -> None:
        self.tool_manager = tool_manager

    async def respond(
        self,
        message: str,
        user: User,
        connections: dict[str, Any],
        access_repository: AccessRepository,
    ) -> dict[str, Any]:
        """Return a chat response, optionally executing an approved tool."""

        normalized = message.strip()
        if not normalized:
            return {
                "answer": "Ask a weather or service question and I will route it through the available tools.",
                "tool": None,
                "arguments": None,
                "result": None,
            }

        if self._is_weather_question(normalized):
            return await self._answer_weather(
                normalized,
                user,
                connections,
                access_repository,
            )

        return {
            "answer": (
                "I can currently route weather, climate, rain, wind, humidity, and umbrella "
                "questions through the connected weather tool."
            ),
            "tool": None,
            "arguments": None,
            "result": None,
        }

    async def _answer_weather(
        self,
        message: str,
        user: User,
        connections: dict[str, Any],
        access_repository: AccessRepository,
    ) -> dict[str, Any]:
        tool_name = "Local Weather REST.get_weather"
        if not any(tool.qualified_name == tool_name for tool in self.tool_manager.list_tools()):
            return {
                "answer": "Connect Local Weather REST and refresh discovery before asking weather questions.",
                "tool": tool_name,
                "arguments": None,
                "result": None,
            }

        location = self._extract_location(message)
        if location is None:
            return {
                "answer": "Which location should I check?",
                "tool": tool_name,
                "arguments": None,
                "result": None,
            }

        arguments = {"location": location}
        result = await self.tool_manager.execute(
            tool_name,
            arguments,
            user,
            connections,
            access_repository,
        )
        return {
            "answer": self._format_weather_answer(message, location, result),
            "tool": tool_name,
            "arguments": arguments,
            "result": result,
        }

    def _is_weather_question(self, message: str) -> bool:
        lowered = message.lower()
        return any(term in lowered for term in self.WEATHER_TERMS)

    def _extract_location(self, message: str) -> str | None:
        for pattern in self.LOCATION_PATTERNS:
            match = pattern.search(message)
            if match:
                return self._clean_location(match.group(1))
        return None

    def _clean_location(self, value: str) -> str | None:
        location = re.sub(
            r"\b(?:today|tomorrow|now|please|outside|right now|this week)\b",
            "",
            value,
            flags=re.I,
        )
        location = location.strip(" ?!.,")
        return location or None

    def _format_weather_answer(
        self,
        message: str,
        location: str,
        result: Any,
    ) -> str:
        if not isinstance(result, dict):
            return f"Weather for {location}: {result}"

        temperature = result.get("temperature", {})
        weather = result.get("weather", {})
        wind = result.get("wind", {})
        description = weather.get("description") or weather.get("condition") or "conditions unavailable"
        current = temperature.get("current_celsius")
        feels_like = temperature.get("feels_like_celsius")
        wind_speed = wind.get("speed_mps")
        umbrella_note = ""
        if "umbrella" in message.lower() or "rain" in message.lower():
            rainy_text = f"{weather.get('condition', '')} {description}".lower()
            umbrella_note = (
                " Carry an umbrella." if "rain" in rainy_text else " An umbrella does not look necessary from the current conditions."
            )

        parts = [f"{location}: {description}"]
        if current is not None:
            parts.append(f"{current} C")
        if feels_like is not None:
            parts.append(f"feels like {feels_like} C")
        if wind_speed is not None:
            parts.append(f"wind {wind_speed} m/s")
        return ", ".join(parts) + "." + umbrella_note
