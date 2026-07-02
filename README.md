# Enterprise MCP Host

Production-oriented web and Rich CLI host for connecting to multiple Model Context Protocol servers with local authentication, third-party identity support, enterprise SSO readiness, RBAC authorization, discovery, execution controls, and audit logging.

## Architecture

The project follows Clean Architecture:

- `presentation`: FastAPI web app plus Rich CLI screens, menu, and rendering.
- `application`: host orchestration and managers for sessions, servers, tools, resources, and prompts.
- `domain`: pure models, enums, and exceptions.
- `infrastructure`: MCP SDK client adapter, configuration loader, and logging.
- `security`: bcrypt password hashing, JWT service, authentication, SSO helpers, authorization, and session store.
- `persistence`: SQLAlchemy entities, repositories, and MySQL database bootstrap.
- `config`: typed settings and MCP server configuration.
- `utils`: reusable validation and formatting helpers.

## Authentication

Login is required before the menu is shown. Local passwords are hashed with bcrypt and never stored in plaintext. Successful login issues JWT access and refresh tokens, creates an in-memory CLI session, and enforces session timeout.

The data model also supports passwordless federated users from Google, Microsoft, Facebook, and enterprise SSO providers. OAuth2, OIDC, and SAML provider configuration is stored separately from user records. Provider secrets are referenced by environment variable name and are not stored in the database.

Default seeded users:

| Username | Password | Role |
| --- | --- | --- |
| `admin` | `Admin@123` | Administrator |
| `operator` | `Operator@123` | Operator |
| `viewer` | `Viewer@123` | Viewer |

Change these defaults before production rollout.

## Identity And SSO Tables

The database includes these authentication and authorization tables:

- `users`: local and federated users. `password_hash` is nullable for SSO-only accounts.
- `identity_providers`: Google, Microsoft, Facebook, OIDC, OAuth2, and SAML provider metadata.
- `federated_identities`: links external provider subjects to local users.
- `sso_login_sessions`: short-lived state, nonce, redirect, and status tracking for SSO handshakes.
- `roles`, `permissions`, `role_permissions`, `user_roles`: RBAC.
- `audit_logs`: audit trail.
- `server_access`, `tool_permissions`: MCP server and tool access rules.

`AuthenticationService.login_federated` accepts a verified provider profile and provisions or links a user. `SSOService.begin_login` creates a tracked SSO handshake and returns the provider login URL.

## Authorization

RBAC is enforced before server access and tool execution.

Administrator can connect/disconnect servers, execute tools, manage users and roles, view logs, refresh servers, and change configuration.

Operator can connect servers, execute tools, list tools, list resources, and list servers.

Viewer can list servers, list tools, list resources, and view prompts.

## Tool And Server Permissions

Server access rules, tool permissions, and identity provider metadata are loaded from `app/config/servers.json` and seeded into MySQL:

```json
{
  "tool_permissions": {
    "calculator.add": ["Administrator", "Operator"],
    "employee.delete": ["Administrator"]
  }
}
```

The host validates these rules before invoking stdio MCP servers or service-backed adapters such as REST.

## Configuration

Copy `.env.example` to `.env` and edit values:

```powershell
Copy-Item .env.example .env
```

Important settings:

- `app/config/appsettings.json`: default application settings, including the MySQL connection URL.
- `MCP_HOST_DATABASE_URL`: optional environment override for the JSON database URL.
- `MCP_HOST_JWT_SECRET`: production JWT signing secret.
- `MCP_HOST_SESSION_TIMEOUT_MINUTES`: active CLI session timeout.
- `MCP_HOST_ACCESS_TOKEN_MINUTES`: JWT access token duration.
- `MCP_HOST_REFRESH_TOKEN_MINUTES`: refresh token duration.
- `MCP_HOST_WEB_HOST`, `MCP_HOST_WEB_PORT`: optional web server bind overrides.
- `MCP_HOST_WEB_SESSION_COOKIE_SECURE`: set `true` behind HTTPS.
- `GOOGLE_CLIENT_ID`, `MICROSOFT_CLIENT_ID`, `FACEBOOK_CLIENT_ID`: third-party app client IDs.
- `GOOGLE_CLIENT_SECRET`, `MICROSOFT_CLIENT_SECRET`, `FACEBOOK_CLIENT_SECRET`: provider secrets.
- `ENTERPRISE_SSO_*`: SAML/OIDC enterprise SSO metadata.

## Startup

Use Python 3.12 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create the MySQL database before first startup:

```sql
CREATE DATABASE enterprise_mcp_host CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

The same setup SQL is also available at `app/config/mysql_setup.sql`. With your local credentials, set:

```json
{
  "database": {
    "url": "mysql+pymysql://root:root@localhost:3306/enterprise_mcp_host"
  }
}
```

Your JDBC server URL `jdbc:mysql://localhost:3306/` maps to the SQLAlchemy/PyMySQL URL above. The app adds the `enterprise_mcp_host` database name at the end.

On first start, the application creates MySQL tables and seeds roles, permissions, users, identity providers, server access rules, and tool permissions.

## Run The MCP Host

The host is the application shell that authenticates users, connects configured MCP servers/services, discovers tools, and executes authorized calls.

Run the web host:

```powershell
python run_web.py
```

Then open:

```text
http://127.0.0.1:8000
```

Login with one of the seeded users:

| Username | Password | Role |
| --- | --- | --- |
| `admin` | `Admin@123` | Administrator |
| `operator` | `Operator@123` | Operator |
| `viewer` | `Viewer@123` | Viewer |

The web app includes login, dashboard, server connection, discovery refresh, tool execution, resources, prompts, and audit log views.

Run the Rich CLI host instead of the web host:

```powershell
python -m app.presentation.main
```

## Run The MCP Server

This project supports two server styles:

- Service-backed REST servers configured in `app/config/servers.json`.
- Traditional stdio MCP servers launched through the official Python MCP SDK.

The default working REST server is `Local Weather REST`. It points at `http://localhost:8009/weather` and expects the LLM or caller to supply a `location` query argument. For example, `location=London` calls `http://localhost:8009/weather?location=London`. Start your local weather API on port `8009` before connecting it from the host.

The weather tool is described for model-driven selection. An LLM should call `Local Weather REST.get_weather` when the user asks about weather, climate, temperature, rain, wind, humidity, outdoor conditions, or questions like "Should I carry an umbrella today?" The LLM should extract the location from the user's request and pass it as `location`; if no location is available, it should ask a follow-up question before calling the tool.

To use it from the host:

1. Start the web or CLI host.
2. Login as `admin` or `operator`.
3. Connect `Local Weather REST`.
4. Refresh discovery.
5. Execute tool `Local Weather REST.get_weather` with a model-supplied or user-supplied location:

```json
{
  "location": "London"
}
```

For stdio MCP servers, add or keep entries like this in `app/config/servers.json`:

```json
{
  "name": "Weather Server",
  "command": "python",
  "args": ["-m", "weather_mcp_server"],
  "env": {},
  "allowed_roles": ["Administrator", "Operator"],
  "timeout_seconds": 30
}
```

When the host connects this server, it starts the configured command over stdio and initializes an MCP SDK client session.

## Run The MCP Client

The host uses `app/infrastructure/mcp_client.py` as its MCP client adapter. You normally exercise it through the web or CLI host, but you can smoke test the REST-backed client directly:

```powershell
@'
import asyncio
from app.config.settings import get_settings
from app.infrastructure.configuration import ConfigurationLoader
from app.infrastructure.mcp_client import MCPServerConnection

async def main():
    servers, _, _ = ConfigurationLoader(get_settings()).load()
    server = next(item for item in servers if item.name == "Local Weather REST")
    connection = MCPServerConnection(server)
    await connection.connect()
    print([tool.qualified_name for tool in await connection.list_tools()])
    print(await connection.call_tool("get_weather", {"location": "London"}))
    await connection.close()

asyncio.run(main())
'@ | python -
```

Expected output includes:

```text
['Local Weather REST.get_weather']
```

## Debug The Complete App

Use this flow when you need to debug the full application path: settings, database bootstrap, authentication, web or CLI presentation, MCP server connection, tool discovery, tool execution, and audit logging.

### 1. Prepare The Debug Environment

Use Python 3.12 or newer and activate the project virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy and edit local environment settings:

```powershell
Copy-Item .env.example .env
```

Confirm the effective configuration source before starting the app:

- `app/config/appsettings.json` contains default settings.
- `.env` can override settings with `MCP_HOST_*` variables.
- `MCP_HOST_DATABASE_URL` must point at a reachable MySQL database.
- `MCP_HOST_WEB_HOST` and `MCP_HOST_WEB_PORT` control the web bind address.
- `app/config/servers.json` controls MCP/REST server definitions, tool permissions, and identity providers.

### 2. Verify Database Bootstrap

Create the database if it does not already exist:

```sql
CREATE DATABASE enterprise_mcp_host CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Then run this import/bootstrap smoke test from the repository root:

```powershell
python -c "from app.presentation.web.main import create_app; app=create_app(); print(app.title)"
```

Expected output:

```text
Enterprise MCP Host
```

If startup fails with a database error, check:

- MySQL is running.
- The database exists.
- The username and password in `MCP_HOST_DATABASE_URL` or `app/config/appsettings.json` are correct.
- The URL uses SQLAlchemy format, for example `mysql+pymysql://root:root@localhost:3306/enterprise_mcp_host`.

### 3. Debug The Web App

Start the FastAPI web host:

```powershell
python run_web.py
```

Open:

```text
http://127.0.0.1:8000
```

Use a debugger by setting breakpoints in:

- `run_web.py` for web startup.
- `app/presentation/web/main.py` for FastAPI lifespan and app creation.
- `app/presentation/web/routes.py` for request handling.
- `app/application/host.py` for application initialization, login, server connection, discovery, and tool calls.
- `app/persistence/repositories.py` for user, role, permission, and audit log persistence.

For auto-reload while debugging route or template changes, run Uvicorn directly:

```powershell
python -m uvicorn app.presentation.web.main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Debug The CLI App

Run the Rich CLI host:

```powershell
python -m app.presentation.main
```

Use a debugger by setting breakpoints in:

- `app/presentation/main.py` for CLI startup and login flow.
- `app/presentation/menu.py` for menu actions.
- `app/presentation/screens.py` for prompt/input screens.
- `app/application/host.py` for shared application behavior used by both CLI and web.

Login with `admin` / `Admin@123` for the broadest permission coverage during local debugging.

### 5. Debug MCP Server Discovery And Tool Execution

The default local REST tool expects a weather service at:

```text
http://localhost:8009/weather?location=London
```

Start that service before connecting `Local Weather REST` from the web or CLI host. Then use this flow:

1. Login as `admin` or `operator`.
2. Connect `Local Weather REST`.
3. Refresh discovery.
4. Confirm `Local Weather REST.get_weather` appears in the tool list.
5. Execute it with:

```json
{
  "location": "London"
}
```

To debug the client layer directly, set breakpoints in:

- `app/infrastructure/configuration.py` for loading `servers.json`.
- `app/infrastructure/mcp_client.py` for REST and stdio MCP connection behavior.
- `app/services/adapters/rest_adapter.py` for REST request construction and response parsing.
- `app/application/server_manager.py` for connect/disconnect behavior.
- `app/application/tool_manager.py` for tool discovery and execution.

You can also run the direct REST-backed client smoke test from the "Run The MCP Client" section to isolate MCP/client problems from the web and CLI layers.

### 6. Debug Authentication, Authorization, And Audit Logs

Use these files when tracing login, permissions, and audit behavior:

- `app/security/auth_service.py` for local and federated login.
- `app/security/password_service.py` for bcrypt verification.
- `app/security/jwt_service.py` for access and refresh token generation.
- `app/security/authorization_service.py` for RBAC checks.
- `app/security/session_store.py` for in-memory sessions.
- `app/persistence/repositories.py` for user, role, permission, and audit persistence.

Application logs are written to:

```text
logs/enterprise_mcp_host.log
```

Watch the log while reproducing an issue:

```powershell
Get-Content logs/enterprise_mcp_host.log -Wait
```

Audit events are also stored in the `audit_logs` MySQL table and can be viewed in the web app with an administrator account.

### 7. Useful Debug Commands

Compile the application modules:

```powershell
python -m compileall app
```

Confirm required runtime dependencies are importable:

```powershell
python -c "import langchain_ollama, langgraph, pypdf, docx; print('deps ok')"
```

Verify document-store search works without MySQL:

```powershell
python -c "from pathlib import Path; from tempfile import TemporaryDirectory; from io import BytesIO; from app.config.settings import Settings; from app.application.document_store import DocumentStore; td=TemporaryDirectory(); store=DocumentStore(Settings(knowledge_base_dir=Path(td.name))); store.add_document('notes.txt', BytesIO(b'Weather service escalation policy for Mumbai support.')); print(store.search('Mumbai policy')[0].filename); td.cleanup()"
```

Use this order when narrowing down failures:

1. `python -m compileall app`
2. Dependency import check.
3. Database bootstrap check.
4. Web startup with `python run_web.py`.
5. CLI startup with `python -m app.presentation.main`.
6. MCP client smoke test.
7. Web or CLI tool execution.
8. Log and audit-log inspection.

## Adding Servers

Edit `app/config/servers.json`:

```json

## Common template 

 {
    "service-name": {
      "name": "",
      "description": "",
      "protocol": "",
      "enabled": true,

      "connection": {},

      "authentication": {},

      "resilience": {},

      "operations": {}, 
      "allowed_roles" : ["Administrator", "Operator"]
    }
  }

## Example for Http
 
    "weather-service": {
      "name": "Weather API",
      "description": "Weather Forecast Provider",
      "protocol": "http",
      "enabled": true,
      "connection": {
        "baseUrl": "https://api.weather.com",
        "timeout": 30,
        "verifySSL": true
      },
      "authentication": {
        "type": "apikey",
        "header": "X-API-Key",
        "value": "${WEATHER_API_KEY}"
      },
      "resilience": {
        "retry": 3,
        "retryDelay": 1000,
        "circuitBreaker": true
      },
      "operations": {
        "forecast": {
          "method": "POST",
          "path": "/weather",
          "query": { "Location": "{city}" }
        }
      },      
      "allowed_roles" : ["Administrator", "Operator"]
}

## Example for gRPC

{
  "protocol": grpc,
  "connection": {
    "host": "employee-service",
    "port": 50051,
    "proto": "employee.proto",
    "package": "employee"
  },
  "operations": {
    "createEmployee": {
      "service": "EmployeeService",
      "method": "CreateEmployee"
    }

  }
}

## Websocket
{
  "protocol": "websocket",
  "connection": {
    "url": "wss://chat.company.com/socket"
  },
  "operations": {
    "sendMessage": {
      "event": "chat.send" 
    } 
  }
}

## STDIO
 
 {
  "protocol": "stdio",
  "connection": {
    "command": [
      "python",
      "weather_server.py" 
    ], 
    "workingDirectory": "./servers/weather"
  }, 
  "operations": {
    "forecast": { 
      "command": "forecast"
    }

  }
}

## SOAP

{
  "protocol": "soap",
  "connection": {
    "wsdl": "https://company.com/service.wsdl"
  },
  "operations": {
    "CreateOrder": {
      "soapAction": "CreateOrder"
    }
  }
}

## GraphQL
{
  "protocol": "graphql", 
  "connection": {
    "endpoint": "https://graphql.company.com/graphql"
  }, 
  "operations": {
    "GetEmployee": { 
      "query": "query GetEmployee($id:Int!){employee(id:$id){name,email}}"
    }
  }
}

## Kafka

{
  "protocol": "kafka",
  "connection": {
    "bootstrapServers": [
      "broker1:9092",
      "broker2:9092"
    ]
  },
  "operations": {
    "publishOrder": {
      "topic": "orders"
    }
  }
}

## RabbitMQ

{
  "protocol": "rabbitmq",
  "connection": {
    "host": "rabbit.company.com",
    "port": 5672
  }, 
  "operations": { 
    "publish": {
      "exchange": "employee", 
      "routingKey": "create"
    }
  }
}

## MQTT

{
  "protocol": "mqtt",
  "connection": {
    "broker": "mqtt.company.com",
    "port": 1883
  },

  "operations": {
    "publishTemperature": { 
      "topic": "sensor/temp"
    } 
  }
}

## SQL Database

{
  "protocol": "database",
  "connection": {
    "engine": "sqlserver", 
    "server": "sql.company.com",
    "port" : ""
    "database": "HR"
  },
  "operations": {
    "GetEmployee": {
      "type": "storedProcedure", 
      "name": "usp_GetEmployee"
    }
  }
}

## SFTP

{
  "protocol": "sftp",
  "connection": {
    "host": "sftp.company.com",
    "port": 22
  },
  "operations": {
    "upload": {
      "remotePath": "/incoming"
    }
  }
}





```

Restart the host so the configuration loader can seed access rules. REST, HTTP, and HTTPS services are handled by `RestAdapter`; stdio entries are handled by the official MCP Python SDK over stdio.

## Adding Users

Local users are managed through `UserRepository` and `PasswordService`. Create the user with a bcrypt hash and assign one or more roles:

```python
user = users.create_user(
    "analyst",
    password_service.hash_password("Strong@123"),
    email="analyst@example.com",
)
users.assign_role(user, "Viewer")
```

Federated users are created with `password_hash=None` after the provider token or SAML assertion has been verified.

## Adding Identity Providers

Add OAuth2/OIDC/SAML providers to `app/config/servers.json` under `identity_providers`. The default file includes Google, Microsoft, Facebook, and `enterprise-sso`. Store client secrets in environment variables and set `client_secret_ref` to the variable name.

## Adding Roles

Add a role through `UserRepository.get_or_create_role`, then assign permission codes with `RoleRepository.assign_permissions`. Built-in permission codes live in `app/domain/enums.py`.

## Adding Permissions

Add new permission codes to `PermissionCode`, seed them in `DataSeeder.ROLE_PERMISSIONS`, and call `AuthorizationService.require_permission` at the application boundary that protects the behavior.

## Audit Logging

Audit records are stored in the `audit_logs` table and written for login, logout, auth failures, server connection, refresh, tool execution, and errors. The schema includes timestamp, username, placeholder IP, success flag, details, and execution duration.

## Extending The Application

The application layer is intentionally independent of Rich and SQLAlchemy details. Add new use cases by creating an application manager or extending an existing manager, then call it from the presentation layer. Keep security checks in the application layer before infrastructure calls.

## Deployment

Recommended production steps:

- Replace default credentials and JWT secret.
- Use a managed MySQL service with TLS, backups, monitoring, and restricted network access.
- Configure centralized log shipping for `logs/enterprise_mcp_host.log`.
- Pin dependency versions after validation.
- Run the CLI under a managed workstation profile or controlled operations host.
- Store secrets in a vault instead of `.env`.

## Future LLM Integration

The host exposes discovered tools with descriptions and JSON schemas that an LLM can use for tool selection and argument generation. A future application-layer `LLMOrchestrator` should receive discovered tools/resources/prompts from the existing managers, apply the same authorization checks, and only then expose approved capabilities to the model context.
