# Roadmap

## Summary

The project should be built in seven explicit stages. Each stage produces a concrete artifact and unlocks the next one. The critical path is the internal bridge: without a proven Resolve Free bridge, higher-level MCP work is not yet trustworthy.

## Stage 1: Documentation and Research

Objective:
Lock the architecture, references, tool taxonomy, risks, and dev conventions.

Dependencies:
None.

Deliverable:

- project `README.md`
- architecture, references, roadmap, tools, development, and risks docs

Exit criteria:

- docs describe one coherent Free-first architecture
- Studio-only external scripting is explicitly excluded as a base assumption
- MVP tool set and bridge contract are defined

## Stage 2: Minimal Backend Bridge for Resolve Free

Objective:
Prove that an external backend can exchange structured commands with an internal Resolve executor.

Dependencies:
Stage 1.

Deliverable:

- bridge contract models
- minimal `file_queue` adapter
- executor bootstrap inside Resolve Free
- one read-only handshake command such as `resolve_health`

Exit criteria:

- backend submits a command and receives a correlated result
- timeout and bridge-unavailable paths are handled
- command/result schema is stable enough for tool integration

## Stage 3: Basic MCP Tools

Objective:
Expose the first low-level MCP tools over a stable backend command contract.

Dependencies:

- Stage 1
- Stage 2 and its stable backend command contract

Deliverable:

- MCP server over `stdio`
- initial tool registrations
- validation and error normalization from MCP input to backend command

Exit criteria:

- at least the system/project foundation tools work end to end
- tool schemas are Pydantic-backed and JSON-schema-friendly
- MCP transport and backend remain clearly separated

## Stage 4: Core Coverage for Projects, Media, and Timeline

Objective:
Add the minimum practical Resolve operations needed for everyday structural automation.

Dependencies:

- Stage 1
- Stage 2
- Stage 3 and its tool taxonomy

Deliverable:

- project tools
- media browsing/import tools
- timeline creation/listing/append tools
- first marker operation

Exit criteria:

- core project/media/timeline scenarios work against the live bridge
- all added operations stay within the approved low-level scope
- failures surface as stable error categories

## Stage 5: Stabilization and Testing

Objective:
Make the bridge and tool layer resilient enough for repeated real-world use.

Dependencies:

- live bridge prototypes and tools from Stages 2-4

Deliverable:

- unit tests for contracts and backend logic
- adapter tests
- manual integration checklists
- restart/recovery handling notes

Exit criteria:

- bridge behavior is tested for timeout, unavailable executor, and malformed response paths
- manual Resolve integration checks are documented
- known limitations are recorded rather than hidden

## Stage 6: Toolset Expansion

Objective:
Expand the low-level and composed tool surface after the substrate is stable.

Dependencies:

- stable low-level substrate from Stages 2-5

Deliverable:

- additional media pool operations
- more timeline inspection/mutation tools
- first composed workflow tools built from low-level commands

Exit criteria:

- new tools reuse existing contracts rather than bypassing the backend
- composed tools remain auditable and predictable
- scope growth does not force architectural rewrite

## Stage 7: High-Level AI Functions on Top of the Stable Core

Objective:
Add AI-assisted workflows only after the backend, bridge, and low-level tools are dependable.

Dependencies:

- stable low-level substrate from Stages 2-6

Deliverable:

- high-level AI workflows that compile into known low-level commands
- prompt/planner layers if needed
- optional composition/orchestration modules

Exit criteria:

- AI tools depend on the same backend and bridge contracts as manual tools
- high-level behavior is observable and debuggable
- no provider-specific coupling is required at the architecture core

## Dependency Chain

```text
Stage 1 -> Stage 2 -> Stage 3 -> Stage 4 -> Stage 5 -> Stage 6 -> Stage 7
```

Key dependency notes:

- Stage 2 depends on Stage 1.
- Stage 3 depends on the stable backend command contract from Stage 2.
- Stage 4 depends on the tool taxonomy from Stage 3.
- Stage 5 depends on live bridge prototypes from Stages 2-4.
- Stages 6 and 7 depend on a stable low-level substrate created by the earlier stages.
