from dependency_injector import containers, providers
from app.services.adapters.base.base_adapter import BaseAdapter
from app.services.adapters.rest_adapter import RestAdapter
from app.domain.enums import Protocol
from app.services.factory.service_factory import ServiceFactory

class ServiceContainer(containers.DeclarativeContainer):
    strategy_map = providers.Dict(
        {
            Protocol.HTTP.value: RestAdapter,
            Protocol.HTTPS.value: RestAdapter,
            Protocol.REST.value: RestAdapter,
        }
    )

    
    service_factory = providers.Factory(
        ServiceFactory,
        strategy_map=strategy_map
    )
