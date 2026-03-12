# Tools

## Summary

The first MCP tool set should stay narrow, low-level, and reliable. The goal is not full Resolve API coverage. The goal is a usable base for project, media, and timeline operations that can later support composed workflows and AI features.

Tool inputs and outputs should be defined with Pydantic models and exposed to MCP as JSON-schema-friendly contracts.

## Design Rules

- Prefer one clear operation per tool.
- Use stable identifiers or explicit selectors in payloads.
- Return structured data, not opaque Resolve objects.
- Keep Free-mode limitations explicit in every tool contract.
- Defer broad or brittle automation until the bridge is proven.

## System and Bridge Tools

### `resolve_health`

Purpose:
Check whether the bridge and internal executor are reachable and whether Resolve is ready.

Minimum inputs:

```json
{}
```

Output contract:

```json
{
  "bridge": {
    "available": true,
    "adapter": "file_queue"
  },
  "executor": {
    "running": true
  },
  "resolve": {
    "connected": true,
    "product_name": "DaVinci Resolve",
    "version": "unknown-or-version"
  },
  "project": {
    "open": true,
    "name": "Current Project"
  }
}
```

Preconditions:
None.

Free-mode notes:
Connection means the internal executor could access Resolve from inside the app, not that external Studio scripting is available.

## Project Tools

### `project_list`

Purpose:
List projects visible to the current Resolve database or folder context.

Minimum inputs:

```json
{}
```

Output contract:

```json
{
  "projects": [
    {
      "name": "Example Project"
    }
  ]
}
```

Preconditions:
Resolve executor is running.

Free-mode notes:
MVP assumes current local database context only.

### `project_open`

Purpose:
Open a project by name.

Minimum inputs:

```json
{
  "project_name": "Example Project"
}
```

Output contract:

```json
{
  "opened": true,
  "project": {
    "name": "Example Project"
  }
}
```

Preconditions:
Project must exist and be accessible in current context.

Free-mode notes:
Cloud and database switching are deferred.

### `project_current`

Purpose:
Return the currently open project.

Minimum inputs:

```json
{}
```

Output contract:

```json
{
  "project": {
    "name": "Current Project"
  }
}
```

Preconditions:
A project must be open.

## Media Tools

### `media_browse`

Purpose:
Browse mounted storage, subfolders, or files visible to Resolve.

Minimum inputs:

```json
{
  "path": "optional-absolute-or-mounted-path"
}
```

Output contract:

```json
{
  "path": "C:/media",
  "subfolders": ["A", "B"],
  "files": ["clip001.mov", "clip002.wav"]
}
```

Preconditions:
Resolve executor is running.

### `media_import`

Purpose:
Import files or folders into the current media pool folder.

Minimum inputs:

```json
{
  "paths": ["C:/media/clip001.mov"]
}
```

Output contract:

```json
{
  "imported_count": 1,
  "items": [
    {
      "name": "clip001.mov"
    }
  ]
}
```

Preconditions:
A project must be open and current media pool context must be available.

Free-mode notes:
MVP should avoid advanced import variants until basic import is stable.

### `media_pool_list`

Purpose:
List clips and subfolders in the current or specified media pool folder.

Minimum inputs:

```json
{
  "folder_path": "optional-logical-media-pool-path"
}
```

Output contract:

```json
{
  "folder": {
    "name": "Master"
  },
  "subfolders": [],
  "clips": [
    {
      "name": "clip001.mov",
      "media_id": "optional-id"
    }
  ]
}
```

Preconditions:
A project must be open.

## Timeline Tools

### `timeline_list`

Purpose:
List timelines in the current project.

Minimum inputs:

```json
{}
```

Output contract:

```json
{
  "timelines": [
    {
      "name": "Assembly",
      "index": 1
    }
  ]
}
```

Preconditions:
A project must be open.

### `timeline_current`

Purpose:
Return the current timeline.

Minimum inputs:

```json
{}
```

Output contract:

```json
{
  "timeline": {
    "name": "Assembly"
  }
}
```

Preconditions:
A project and timeline must be open.

### `timeline_create_empty`

Purpose:
Create an empty timeline.

Minimum inputs:

```json
{
  "name": "Assembly"
}
```

Output contract:

```json
{
  "created": true,
  "timeline": {
    "name": "Assembly"
  }
}
```

Preconditions:
A project must be open.

### `timeline_append_clips`

Purpose:
Append media pool clips to the current or specified timeline.

Minimum inputs:

```json
{
  "timeline_name": "optional-target-timeline",
  "clip_refs": [
    {
      "media_id": "clip-id"
    }
  ]
}
```

Output contract:

```json
{
  "appended": true,
  "count": 1
}
```

Preconditions:
Project must be open, timeline must exist, clip references must resolve.

### `timeline_items_list`

Purpose:
List items in a timeline track.

Minimum inputs:

```json
{
  "track_type": "video",
  "track_index": 1,
  "timeline_name": "optional-target-timeline"
}
```

Output contract:

```json
{
  "items": [
    {
      "item_index": 0,
      "name": "clip001.mov",
      "start_frame": 100,
      "end_frame": 200
    }
  ]
}
```

Preconditions:
Timeline and track must exist.

### `marker_add`

Purpose:
Add a marker to the current timeline or a specific timeline item.

Minimum inputs:

```json
{
  "scope": "timeline",
  "frame": 100,
  "color": "Blue",
  "name": "Review",
  "note": "Check this cut",
  "duration": 1
}
```

Output contract:

```json
{
  "added": true,
  "scope": "timeline"
}
```

Preconditions:
Target timeline or item must resolve.

## Low-Level vs Composite Tools

### Low-level primitives for MVP

- `resolve_health`
- `project_list`
- `project_open`
- `project_current`
- `media_browse`
- `media_import`
- `media_pool_list`
- `timeline_list`
- `timeline_current`
- `timeline_create_empty`
- `timeline_append_clips`
- `timeline_items_list`
- `marker_add`

### Composite tools for later

- import a folder and assemble a timeline
- create timeline from filtered media pool selection
- add review markers from an external metadata file
- build a rough cut from structured clip ranges

## Explicit Deferrals

- render automation breadth
- Fusion-heavy actions
- cloud/database switching
- AI/ML features
- complex edit transforms
- deep color workflows
- long-running media analysis pipelines
