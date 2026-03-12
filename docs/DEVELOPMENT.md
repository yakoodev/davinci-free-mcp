# Development

## Summary

This project should be built as a small, modular Python codebase with MCP at the edge, backend logic in the middle, and Resolve Free execution isolated behind a bridge.

The repository currently starts with documentation and references. The codebase should grow around the architecture already described in the docs, not around a copied reference implementation.

## Intended Repository Structure

```text
src/davinci_free_mcp/
  server/        # MCP server entrypoints, tool registration, transport wiring
  backend/       # command routing, orchestration, result normalization
  bridge/        # bridge contract plus adapter implementations
  resolve_exec/  # internal Resolve executor and command handlers
  contracts/     # Pydantic models for tools, commands, results, errors
  config/        # settings and environment loading
tests/
docs/
references/
```

## Module Ownership

### `server/`

Owns:

- MCP tool declarations
- MCP transport bootstrap
- MCP-facing schemas and descriptions

Must not own:

- direct Resolve API calls
- transport-specific bridge internals

### `backend/`

Owns:

- command orchestration
- precondition checks
- normalization of executor and bridge responses

Must not own:

- embedded Resolve script bootstrap
- MCP transport wiring details

### `bridge/`

Owns:

- bridge interface
- request/result transport handling
- adapter-specific recovery and timeout behavior

Must not own:

- Resolve business logic
- MCP tool schemas

### `resolve_exec/`

Owns:

- in-Resolve bootstrap
- internal command dispatch
- object resolution against Resolve's API
- JSON-safe serialization

Must not own:

- MCP-specific concepts
- external client logic

## Dev Workflow

### Create environment

Recommended baseline:

```bash
uv venv
```

or:

```bash
python -m venv .venv
```

### Install dependencies

Expected dependency profile:

- `mcp`
- `pydantic`
- `pydantic-settings`
- `pytest`

Suggested command shape:

```bash
uv sync
```

or:

```bash
pip install -e .[dev]
```

### Run MCP server in dev mode

Expected target:

```bash
uv run python -m davinci_free_mcp.server.main
```

### Run backend-only tests

Expected target:

```bash
pytest tests/backend -q
```

### Run bridge adapter tests

Expected target:

```bash
pytest tests/bridge -q
```

### Run manual Resolve integration checks

Expected target:

- start Resolve Free
- start the internal executor from Resolve's internal scripting entrypoint
- run backend or MCP commands from the external environment
- verify request/result flow with at least one read-only command

## Testing Strategy

Split testing into three layers:

### Contracts and schemas

- command envelope validation
- result envelope validation
- tool input and output schema checks

### Backend and adapters

- command routing
- timeout handling
- malformed result handling
- bridge unavailable paths

### Manual Resolve integration

- executor bootstrap
- `resolve_health`
- current project lookup
- one timeline or media read operation

## Working With References

References are local source material, not default dependencies.

Rules:

- read the smallest useful subset first
- borrow concepts, contracts, and patterns
- avoid copying entire servers or wrappers
- document any reference-inspired design in our own terms
- keep the codebase independent from local clone layout

## Studio-Only Smell Checklist

Reject or rethink a design if it assumes any of the following:

- external `scriptapp("Resolve")` from the main backend process is the default connection path
- Resolve must expose local or network external scripting for the project to function
- the backend can hold native Resolve objects directly
- full API coverage is required before shipping a narrow workflow
- cloud/database switching is part of MVP
- Fusion- or render-heavy features are required to validate the architecture

## Recommended First Coding Module

Start with:

1. `contracts/`
2. `bridge/`
3. minimal `resolve_exec/` handshake

Reason:
The bridge is the highest-risk unknown. If it cannot be made stable enough, the rest of the stack should not be built on assumptions.
