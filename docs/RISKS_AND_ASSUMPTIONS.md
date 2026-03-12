# Risks and Assumptions

## Confirmed

The following points are grounded in the local references and are strong enough to design around:

- The DaVinci Resolve scripting object model exists and is documented in the local references.
- Internal script execution inside Resolve is plausible and demonstrated by local utility-script examples.
- A Python MCP server and typed backend can be built cleanly using the available MCP and Pydantic references.
- Resolve Free should be treated differently from Studio when defining the integration boundary.

## Hypotheses

The following are reasonable working assumptions but still need prototype validation:

- A stable long-running internal executor can be made practical in Resolve Free.
- `local_http` can function reliably as an internal bridge transport in the embedded environment.
- JSON command/result marshaling can remain deterministic and compact enough for bridge use.
- The executor can re-resolve needed objects on each command without unacceptable performance or complexity.

## Core Resolve Free Constraints

These constraints should remain visible throughout development:

- do not assume Studio-only external scripting is available
- do not assume external `scriptapp("Resolve")` is the correct default integration path
- do not assume every documented Resolve API method is equally safe for MVP
- do not assume long-running background behavior inside Resolve without prototype evidence

## Risks

### Embedded runtime limitations

The internal Python and UI environment inside Resolve may have restrictions that do not show up in ordinary external Python applications.

Possible impact:

- transport adapter instability
- module or import quirks
- event loop limitations
- limited observability when failures happen

### IPC robustness across Resolve restarts

A bridge may fail in partial states when Resolve closes, reloads a project, or restarts unexpectedly.

Possible impact:

- orphaned requests
- stale result files
- false-positive health states
- hung tool calls

### Object identity persistence

Opaque Resolve objects may not be safe to store and reuse across unrelated commands.

Possible impact:

- invalid handles
- hidden state bugs
- hard-to-reproduce failures after project or timeline changes

Recommended mitigation:
Prefer explicit locators and re-resolution over native object persistence.

### UI blocking and deadlock

Poorly designed executor behavior may block Resolve UI interactions or deadlock around long-running operations.

Possible impact:

- unusable editor session
- incomplete responses
- fragile transport behavior

Recommended mitigation:

- keep handlers narrow
- start with read-only commands
- keep timeout and recovery behavior explicit

### Version and platform differences

Behavior may vary by Resolve version, operating system, or local install layout.

Possible impact:

- bootstrap failures
- API availability differences
- adapter-specific instability

## Prototype-Before-Build Areas

These items should be proven early before broad implementation:

### Internal executor bootstrap

Need to prove:

- internal script can start reliably
- executor can access Resolve handle
- executor can return structured health data

### Transport comparison: `file_queue` vs `local_http`

Need to prove:

- both can carry the same command schema
- recovery behavior is understandable
- timeout semantics are implementable

Default expectation:

- `file_queue` is first
- `local_http` is optional until proven worthwhile

### Object lookup and handle strategy

Need to prove:

- practical locators for timelines, media pool items, and markers
- safe behavior when names are ambiguous
- minimal need for cached native objects

### Timeout and recovery semantics

Need to prove:

- backend can distinguish slow executor from unavailable executor
- stale requests and results can be cleaned safely
- user-facing errors can remain stable and actionable

## Working Defaults

Until code proves otherwise, the project should assume:

- documentation language is English
- MVP MCP transport is `stdio`
- `file_queue` is the default bridge adapter
- `local_http` is supported only as a contract-compatible alternative
- first implementation work starts with `bridge_contract` and a minimal `file_queue` handshake
