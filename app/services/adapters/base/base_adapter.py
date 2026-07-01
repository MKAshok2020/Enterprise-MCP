from abc import ABC, abstractmethod
from typing import Any

from app.domain.services_config import Service


class BaseAdapter(ABC):
    """
    Base class for all protocol adapters.
    """

    def __init__(self, service: Service):
        self.service = service

    @abstractmethod
    async def invoke(
        self,
        operation_name: str,
        payload: dict | None = None,
    ) -> Any:
        """
        Invoke an operation on the configured service.

        Args:
            operation_name: Name of the configured operation.
            payload: Request payload.

        Returns:
            Response from the remote service.
        """
        raise NotImplementedError()

    async def connect(self) -> None:
        """
        Optional connection initialization.

        Override for adapters like:
        - Kafka
        - RabbitMQ
        - MQTT
        - WebSocket
        """
        return

    async def disconnect(self) -> None:
        """
        Optional connection cleanup.
        """
        return

    async def close(self) -> None:
        """
        Default implementation.
        """
        await self.disconnect()
