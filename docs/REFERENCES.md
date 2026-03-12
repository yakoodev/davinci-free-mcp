# References

## Summary

This repository already contains local reference repositories. They are here to inform architecture, API boundaries, typing, and implementation patterns. They are **not** intended to become hard dependencies by default.

Use them selectively:

- adopt patterns, not code wholesale
- prefer the smallest reusable idea
- reject assumptions that depend on DaVinci Resolve Studio external scripting

## Primary References

### `references/python-sdk`

Category:
MCP architecture

Why it matters:

- main Python reference for MCP server structure
- shows tool registration, context injection, transport configuration, and structured outputs
- best source for how the Python MCP stack should look in this project

Read first:

- `README.v2.md`
- `src/mcp/server/mcpserver/server.py`
- `src/mcp/server/mcpserver/tools/base.py`

Use as:
Primary MCP architecture reference.

Risk of over-adopting:
Pulling in advanced MCP features before tools and bridge are stable.

### `references/davinci-resolve-api`

Category:
Resolve scripting/API surface

Why it matters:

- concise reference for the official Resolve object model
- good entry point for project/media/timeline classes and common method names

Read first:

- `README.md`
- `Modules/DaVinciResolveScript.py`
- `Examples/python_get_resolve.py`

Use as:
Resolve API surface reference.

Risk of over-adopting:
Treating documented external invocation paths as valid for Resolve Free architecture.

### `references/davinci-resolve/docs`

Category:
Resolve scripting/API surface

Why it matters:

- easier-to-scan method inventory for Resolve classes
- useful for tool taxonomy and contract design

Read first:

- `resolve-python-api.md`
- `quick-reference.md`
- `Davinci Resolve Scripting README.txt`

Use as:
Practical method catalog and validation reference.

Risk of over-adopting:
Assuming every documented method is equally safe or useful for MVP.

### `references/Clip_Assassin_Resolve`

Category:
Resolve Free internal scripting/workarounds

Why it matters:

- strongest local proof that Resolve Free can be approached through internal scripting
- demonstrates running via `Workspace -> Scripts`
- documents the distinction between Free and Studio clearly
- shows the embedded environment pattern using `app.GetResolve()`

Read first:

- `README.md`
- `clip_assassin_free.py`
- `resolve_core.py`

Use as:
Main Free-compatible execution reference and feasibility proof.

Risk of over-adopting:
Inheriting one-off UI utility script assumptions into reusable backend architecture.

### `references/pybmd`

Category:
Wrappers/types/stubs

Why it matters:

- demonstrates typed wrapper organization around Resolve objects
- useful for naming, wrapper boundaries, and version-aware thinking

Read first:

- `README.md`
- `pybmd/resolve.py`
- `pybmd/_wrapper_base.py`

Use as:
Wrapper and typing design reference.

Risk of over-adopting:
Wrapping too much API surface before proving the bridge.

### `references/fusionscript-stubs`

Category:
Wrappers/types/stubs

Why it matters:

- provides type hints for Resolve/Fusion scripting objects
- useful for editor support and future static typing

Read first:

- `README.md`
- `fusionscript-stubs/`

Use as:
Typing and autocomplete aid.

Risk of over-adopting:
Assuming type availability means runtime behavior is stable.

## Secondary References

### `references/davinci-resolve-mcp`

Category:
MCP architecture plus Resolve tool taxonomy

Why it matters:

- useful for grouping related actions into compound tools
- good example of lazy connection checks, tool taxonomy, and JSON-safe serialization

Read first:

- `README.md`
- `src/server.py`

Use as:
Idea source for tool naming, grouping, and response normalization.

Risk of over-adopting:
Building the wrong system for Resolve Free because it is Studio/external-scripting centric.

### `references/pydavinci`

Category:
Wrappers/types/stubs

Why it matters:

- another typed wrapper perspective
- useful for wrapper ergonomics

Read first:

- `README.md`

Use as:
Secondary wrapper reference only.

Risk of over-adopting:
It is explicitly oriented around external scripting workflows.

### `references/resolve_helper_scripts`

Category:
Resolve Free internal scripting/workarounds

Why it matters:

- shows utility-script-style automation patterns
- demonstrates practical in-Resolve scripting usage

Read first:

- `README.md`
- `resolve_importer.py`
- `resolve_fun.py`

Use as:
Source of operational ideas for internal scripting.

Risk of over-adopting:
Inheriting ad hoc script structure where a reusable executor is needed.

### `references/pydantic-settings`

Category:
Config/schema/orchestration

Why it matters:

- strong reference for layered config loading and Pydantic-based settings

Read first:

- `README.md`

Use as:
Settings and config design reference.

Risk of over-adopting:
Adding configuration complexity before core runtime behavior is proven.

## Reference Usage Rules

Use these references with the following priorities:

1. `python-sdk` for MCP shape
2. `davinci-resolve-api` and `davinci-resolve/docs` for Resolve object model
3. `Clip_Assassin_Resolve` for Free-compatible internal execution constraints
4. `pybmd` and `fusionscript-stubs` for wrappers and typing
5. `pydantic-settings` for config design

## What Not to Do

Do not:

- vendor large chunks of the reference repos into `src/`
- add them all as dependencies
- copy a Studio-oriented server and rename it
- treat complete API coverage as the MVP goal
- assume undocumented Free behavior is guaranteed unless prototyped locally
