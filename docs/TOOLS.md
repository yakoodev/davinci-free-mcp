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

### `project_manager_folder_list`

Purpose:
Return the current project-manager folder, its direct child folders, and visible projects.

### `project_manager_folder_open`

Purpose:
Switch into a direct child folder in the current project-manager context.

### `project_manager_folder_up`

Purpose:
Move the project-manager context to its parent folder.

### `project_manager_folder_path`

Purpose:
Return the current project-manager folder with breadcrumb path, child folders, and visible projects.

## Media Tools

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
List clips and subfolders in the current media pool folder.

Minimum inputs:

```json
{}
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
      "name": "clip001.mov"
    }
  ]
}
```

Preconditions:
A project must be open.

### `media_pool_folder_open`

Purpose:
Switch into a direct child media pool folder from the current folder context.

### `media_pool_folder_create`

Purpose:
Create a direct child media pool folder under the current folder and switch into it.

### `media_pool_folder_up`

Purpose:
Move the current media pool folder context to its parent folder.

### `media_clip_inspect`

Purpose:
Inspect one clip from the current media pool folder and return its clip properties.

Minimum inputs:

```json
{
  "clip_name": "clip001.mov"
}
```

Output contract:

```json
{
  "folder": {
    "name": "Master"
  },
  "clip": {
    "name": "clip001.mov",
    "properties": {
      "File Path": "C:/media/clip001.mov"
    }
  }
}
```

Preconditions:
A project must be open and the clip name must resolve uniquely in the current media pool folder.

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
  "clip_names": ["clip001.mov"]
}
```

Output contract:

```json
{
  "timeline": {
    "name": "Assembly",
    "index": 1
  },
  "appended": true,
  "count": 1,
  "clip_names": ["clip001.mov"]
}
```

Preconditions:
Project must be open, timeline must exist, clip names must resolve in the current media pool folder.

### `timeline_create_from_clips`

Purpose:
Create a new timeline from media pool clips resolved in the current media pool folder.

Minimum inputs:

```json
{
  "name": "Assembly",
  "clip_names": ["clip001.mov"]
}
```

Output contract:

```json
{
  "created": true,
  "timeline": {
    "name": "Assembly",
    "index": 1
  },
  "count": 1,
  "clip_names": ["clip001.mov"]
}
```

Preconditions:
Project must be open and clip names must resolve uniquely in the current media pool folder.

### `timeline_items_list`

Purpose:
List grouped items across all video and audio tracks in the current or specified timeline.

Minimum inputs:

```json
{
  "timeline_name": "optional-target-timeline"
}
```

Output contract:

```json
{
  "project": {
    "name": "Current Project",
    "open": true
  },
  "timeline": {
    "name": "Assembly",
    "index": 1
  },
  "tracks": [
    {
      "track_type": "video",
      "track_index": 1,
      "items": [
        {
          "item_index": 0,
          "name": "clip001.mov",
          "start_frame": 100,
          "end_frame": 200
        }
      ]
    }
  ]
}
```

Preconditions:
Timeline and track must exist.

## Marker Tools

### `marker_add`

Purpose:
Add a marker to the current or specified timeline.

### `marker_list`

Purpose:
List markers on the current or specified timeline.

Minimum inputs:

```json
{
  "timeline_name": "optional-target-timeline"
}
```

Output contract:

```json
{
  "project": {
    "name": "Current Project",
    "open": true
  },
  "timeline": {
    "name": "Assembly",
    "index": 1
  },
  "markers": [
    {
      "frame": 100,
      "color": "Blue",
      "name": "Review",
      "note": "Check this edit",
      "duration": 12,
      "custom_data": ""
    }
  ]
}
```

### `marker_delete`

Purpose:
Delete a marker by frame on the current or specified timeline.

## Low-Level vs Composite Tools

### Low-level primitives for MVP

- `resolve_health`
- `project_list`
- `project_manager_folder_list`
- `project_manager_folder_open`
- `project_manager_folder_up`
- `project_manager_folder_path`
- `project_open`
- `project_current`
- `media_import`
- `media_pool_list`
- `media_pool_folder_open`
- `media_pool_folder_create`
- `media_pool_folder_up`
- `media_clip_inspect`
- `timeline_list`
- `timeline_current`
- `timeline_create_empty`
- `timeline_set_current`
- `timeline_append_clips`
- `timeline_create_from_clips`
- `timeline_items_list`
- `marker_add`
- `marker_list`
- `marker_delete`

### Composite tools for later

- import a folder and assemble a timeline
- add review markers from an external metadata file
- build a rough cut from structured clip ranges

## Explicit Deferrals

- `media_browse`
- render automation breadth
- Fusion-heavy actions
- cloud/database switching
- AI/ML features
- complex edit transforms
- deep color workflows
- long-running media analysis pipelines
