from app.domain.enums import TransportType

class TransportFactory:

    async def connect(self, server_config):
        if server_config.transport == TransportType.STDIO:
            return await self._connect_stdio(server_config)

        if server_config.transport == TransportType.HTTP:
            return await self._connect_http(server_config)

        raise ValueError(f"Unsupported transport: {server_config.transport}")