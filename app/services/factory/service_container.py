from dependency_injector import containers, providers
from ..adapters.base.base_adapter import BaseAdapter
from ..adapters.rest_adapter import RestAdapter
from ..adapters.models.enums import ServiceProtocol
from ..factory.service_factory import ServiceFactory

class ServiceContainer(containers.DeclarativeContainer):
    strategy_map = providers.Dict({
        ServiceProtocol.HTTP.value , providers.Factory(RestAdapter)
    })

    
    service_factory = providers.Factory(
        ServiceFactory,
        strategy_map=strategy_map
    )