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

The host validates these rules before invoking the MCP SDK.

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
python -m app.presentation.main
```

Run the web application:

```powershell
python run_web.py
```

Then open:

```text
http://127.0.0.1:8000
```

The web app includes login, dashboard, server connection, discovery refresh, tool execution, resources, prompts, and audit log views.

Create the MySQL database before first startup:

```sql
CREATE DATABASE enterprise_mcp_host CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
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

Restart the host so the configuration loader can seed access rules. The MCP adapter uses the official Python SDK over stdio.

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

The host intentionally does not call an LLM today. Future integration should add an application-layer `LLMOrchestrator` that receives discovered tools/resources/prompts from the existing managers, applies the same authorization checks, and only then exposes approved capabilities to the model context.
