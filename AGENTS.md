# AGENTS

## Project overview

This repository is an enterprise MCP host built around a Clean Architecture layout:

- `app/presentation`: web and CLI entrypoints
- `app/application`: orchestration, managers, and AI workflow logic
- `app/domain`: pure models, enums, and exceptions
- `app/infrastructure`: adapters, configuration, and logging
- `app/security`: authentication, authorization, JWT, and session behavior
- `app/persistence`: SQLAlchemy models and repositories
- `app/config`: settings and server configuration

The current AI orchestration pattern is LangGraph-first. The chat flow is delegated through `ChatManager`, which instantiates a dedicated `LangGraphAgent` graph in `app/application/langgraph_agent.py` and routes through `model -> tools -> model` cycles as needed.

## Key conventions

- Keep domain code free of framework-specific dependencies.
- Prefer manager/service composition in `app/application` over direct logic in presentation code.
- Use `Host` as the composition root for dependencies.
- Keep settings strongly typed in `app/config/settings.py`.
- The app uses `unittest` for repository and architecture regression checks; do not switch the test suite to pytest without an explicit repo-wide decision.

## Build and validation

Run from the repository root:

```powershell
python -m unittest tests.test_chat_history_persistence tests.test_langgraph_architecture
```

For the web app:

```powershell
python run_web.py
```

## Important files

- `README.md`: project overview, setup, runtime instructions, and configuration
- `app/application/chat_manager.py`: user-facing chat orchestration and integration with history
- `app/application/langgraph_agent.py`: LangGraph node graph for model/tool execution
- `app/application/host.py`: composition root and service wiring
- `app/application/tool_manager.py`: tool discovery and authorization
- `app/application/document_store.py`: document indexing and retrieval

## Working rules for agents

- Preserve the Clean Architecture boundaries when adding new features.
- If the change affects chat behavior, update the graph-based orchestration rather than adding ad hoc branching in the presentation layer.
- Prefer minimal, targeted edits and validate with the relevant unit tests.
- When adding new tools or document-backed features, keep the tool schema and authorization checks aligned with the existing `ToolDefinition` model and `ToolManager` flow.
- Prefer the existing patterns in `README.md` and the application managers over inventing a parallel architecture.
