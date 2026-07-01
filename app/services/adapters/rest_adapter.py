import asyncio
from typing import Any

import httpx

from .base.base_adapter import BaseAdapter
from .base.exceptions import (
    AdapterException,
    AuthenticationException,
    ServiceException,
    TimeoutException,
)
from .models.enums import AuthenticationType, HttpMethod
from .models.services_config import Operation, Service 


class RestAdapter(BaseAdapter):

    def __init__(self, service: Service):

        super().__init__(service)

        self.service = service

        self.connection = service.connection

        self.base_url = self.connection.base_url.rstrip("/")

        self.timeout = self.connection.timeout

        self.verify_ssl = self.connection.verify_ssl

        self.authentication = service.authentication

        self.resilience = service.resilience

    async def invoke(
        self,
        operation_name: str,
        payload: dict | None = None,
    ) -> Any:

        payload = payload or {}

        operation = self._get_operation(operation_name)

        method = operation.method.value

        path = self._replace_path_params(
            operation.path,
            payload,
        )

        url = f"{self.base_url}{path}"

        params = self._build_query(
            operation,
            payload,
        )

        headers = self._build_headers()

        headers.update(operation.headers)

        body = payload.get("body")

        retries = self.resilience.retry if self.resilience else 0

        retry_delay = (
            self.resilience.retry_delay
            if self.resilience
            else 1
        )

        for attempt in range(retries + 1):

            try:

                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                ) as client:

                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        headers=headers,
                        json=body,
                    )

                    if response.status_code == 401:
                        raise AuthenticationException(
                            response.text
                        )

                    response.raise_for_status()

                    if not response.content:
                        return None

                    content_type = response.headers.get(
                        "content-type",
                        "",
                    )

                    if "application/json" in content_type:
                        return response.json()

                    return response.text

            except httpx.TimeoutException as ex:

                if attempt == retries:
                    raise TimeoutException(str(ex))

                await asyncio.sleep(retry_delay)

            except httpx.HTTPStatusError as ex:

                raise ServiceException(str(ex))

            except Exception as ex:

                if attempt == retries:
                    raise AdapterException(str(ex))

                await asyncio.sleep(retry_delay)

    def _get_operation(
        self,
        operation_name: str,
    ) -> Operation:

        operation = self.service.operations.get(operation_name)

        if operation is None:
            raise AdapterException(
                f"Operation '{operation_name}' not found."
            )

        if operation.method is None:
            raise AdapterException(
                f"Operation '{operation_name}' does not define an HTTP method."
            )

        if operation.path is None:
            raise AdapterException(
                f"Operation '{operation_name}' does not define a path."
            )

        return operation

    @staticmethod
    def _replace_path_params(
        path: str,
        payload: dict,
    ) -> str:

        for key, value in payload.items():
            path = path.replace(
                f"{{{key}}}",
                str(value),
            )

        return path

    @staticmethod
    def _build_query(
        operation: Operation,
        payload: dict,
    ) -> dict:

        query = {}

        for key, value in operation.query.items():

            if (
                value.startswith("{")
                and value.endswith("}")
            ):
                param = value[1:-1]
                query[key] = payload.get(param)
            else:
                query[key] = value

        return query

    def _build_headers(self) -> dict:

        headers = {
            "Content-Type": "application/json"
        }

        auth = self.authentication

        if auth is None:
            return headers

        match auth.type:

            case AuthenticationType.API_KEY:

                headers[auth.header] = auth.value

            case AuthenticationType.BEARER:

                headers["Authorization"] = (
                    f"Bearer {auth.token}"
                )

            case AuthenticationType.BASIC:

                import base64

                token = base64.b64encode(
                    f"{auth.username}:{auth.password}".encode()
                ).decode()

                headers["Authorization"] = (
                    f"Basic {token}"
                )

        return headers