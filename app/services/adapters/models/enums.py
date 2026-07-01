
from enum import StrEnum


class Protocol(StrEnum):
    HTTP = "http"
    HTTPS = "https"
    REST = "rest"
    GRPC = "grpc"
    SOAP = "soap"
    GRAPHQL = "graphql"
    WEBSOCKET = "websocket"
    STDIO = "stdio"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    MQTT = "mqtt"
    DATABASE = "database"
    FTP = "ftp"
    SFTP = "sftp"
    REDIS = "redis"
    CUSTOM = "custom"

class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class AuthenticationType(StrEnum):
    NONE = "none"
    API_KEY = "apikey"
    BASIC = "basic"
    BEARER = "bearer"
    OAUTH2 = "oauth2"
    CERTIFICATE = "certificate"
    

