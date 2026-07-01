from ..adapters.base.base_adapter import BaseAdapter
from app.domain.services_config import Service


class ServiceFactory:
    def __init__(self, strategy_map: dict[str, BaseAdapter]):
        self._strategy_map = strategy_map

    def get_service(self, service_ : Service) -> BaseAdapter:
        # Pull from the injected dictionary safely
        adapter_ = self._strategy_map.get(service_.protocol) or self._strategy_map.get(
            service_.protocol.value
        )
        if not adapter_:
            raise ValueError(f"No adapter registered for protocol: {service_.protocol}")
        return adapter_(service_)
