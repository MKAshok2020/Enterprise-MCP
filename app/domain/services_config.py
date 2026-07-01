from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AuthenticationType, HttpMethod, Protocol

# ---------------------------------------------------------
# Base Model
# ---------------------------------------------------------

class ConfigModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        validate_assignment=True
    )

# ---------------------------------------------------------
# Connection
# ---------------------------------------------------------

class Connection(BaseModel):

    base_url: Optional[str] = Field(default=None, alias="baseUrl")
    verify_ssl: bool = Field(default=True, alias="verifySSL")
    timeout: int = 30 
    #Generic
    host: Optional[str] = None
    port: Optional[int] = None
    # STDIO
    command: Optional[List[str]] = None
    working_directory: Optional[str] = Field(
        default=None,
        alias="workingDirectory"
    )

    # Kafka
    bootstrap_servers: Optional[List[str]] = Field(
        default=None,
        alias="bootstrapServers"
    )

    # Database
    database: Optional[str] = None

    # SOAP
    wsdl: Optional[str] = None

    # GraphQL
    endpoint: Optional[str] = None

# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------

class Authentication(ConfigModel):

    type: AuthenticationType = AuthenticationType.NONE

    username: Optional[str] = None
    password: Optional[str] = None

    token: Optional[str] = None

    header: Optional[str] = None
    value: Optional[str] = None

    client_id: Optional[str] = Field(
        default=None,
        alias="clientId"
    )

    client_secret: Optional[str] = Field(
        default=None,
        alias="clientSecret"
    )

    token_url: Optional[str] = Field(
        default=None,
        alias="tokenUrl"
    )

# ---------------------------------------------------------
# Resilience
# ---------------------------------------------------------

class Resilience(ConfigModel):

    retry: int = 0

    retry_delay: int = Field(
        default=0,
        alias="retryDelay"
    )

    circuit_breaker: bool = Field(
        default=False,
        alias="circuitBreaker"
    )

    max_connections: int = Field(
        default=100,
        alias="maxConnections"
    )


# ---------------------------------------------------------
# Operation
# ---------------------------------------------------------

class Operation(ConfigModel):

    # HTTP
    method: Optional[HttpMethod] = None

    path: Optional[str] = None

    query: Dict[str, str] = Field(
        default_factory=dict
    )

    headers: Dict[str, str] = Field(
        default_factory=dict
    )

    # GraphQL
    graphql: Optional[str] = None

    # SOAP
    soap_action: Optional[str] = Field(
        default=None,
        alias="soapAction"
    )

    # gRPC
    service: Optional[str] = None

    rpc: Optional[str] = None

    # Kafka / MQTT
    topic: Optional[str] = None

    # RabbitMQ
    exchange: Optional[str] = None

    routing_key: Optional[str] = Field(
        default=None,
        alias="routingKey"
    )

    # Database
    sql: Optional[str] = None

    stored_procedure: Optional[str] = Field(
        default=None,
        alias="storedProcedure"
    )

    # STDIO
    command: Optional[str] = None

    # Custom protocol support
    properties: Dict[str, Any] = Field(
        default_factory=dict
    )


# ---------------------------------------------------------
# Service
# ---------------------------------------------------------

class Service(ConfigModel):

    name: str

    description: Optional[str] = None

    version: str = "1.0"

    protocol: Protocol

    enabled: bool = True

    tags: List[str] = Field(
        default_factory=list
    )

    connection: Connection

    authentication: Optional[Authentication] = None

    resilience: Optional[Resilience] = None

    operations: Dict[str, Operation] = Field(
        default_factory=dict
    )


# ---------------------------------------------------------
# Root Configuration
# ---------------------------------------------------------

class ServiceConfiguration(ConfigModel):

    version: str = "1.0"

    services: Dict[str, Service] = Field(
        default_factory=dict
    )
