# Tools

## Summary

The current MCP tool set is intentionally split into two layers:

- low-level Resolve tools that cross the bridge into the embedded executor
- local media-analysis tools that run in the backend and emit structured artifacts for later edit planning

The goal is still not full Resolve API coverage. The goal is a usable base for project, media, timeline, marker, and analysis workflows that can later support composed and domain-specific features.

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

### Additional media-pool tools already implemented

The current codebase also exposes:

- `media_pool_folder_root`
- `media_pool_folder_path`
- `media_pool_folder_list_recursive`
- `media_pool_folder_open_path`
- `media_clip_inspect_path`

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

### `timeline_clips_place`

Purpose:
Place one or more clips into the current or specified timeline with explicit record timing.

Clip selector modes:

- `clip_name`: resolves in the current media pool folder
- `media_pool_path`: resolves by folder path, either absolute from the root media pool or relative from the current folder

Selector precedence and compatibility:

- when `media_pool_path` is a non-empty string, path-based resolution is used
- otherwise the tool falls back to `clip_name`
- this keeps the older `clip_name` workflow valid for clients that send an empty `media_pool_path`

Minimum inputs:

```json
{
  "placements": [
    {
      "clip_name": "clip001.mov",
      "record_frame": 100,
      "track_index": 1
    }
  ]
}
```

Path-oriented example:

```json
{
  "placements": [
    {
      "media_pool_path": "/Master/Shots/clip001.mov",
      "record_frame": 100,
      "track_index": 1,
      "start_frame": 0,
      "end_frame": 24
    }
  ]
}
```

Path syntax:

- absolute path from the root media pool: `"/Master/Shots/clip001.mov"`
- relative path from the current folder: `"Shots/clip001.mov"`

Output contract:

```json
{
  "project": {
    "open": true,
    "name": "Demo Project"
  },
  "timeline": {
    "name": "Assembly",
    "index": 1
  },
  "placed_count": 1,
  "items": [
    {
      "item_index": 0,
      "name": "clip001.mov",
      "track_type": "video",
      "track_index": 1,
      "start_frame": 100,
      "end_frame": 124
    }
  ]
}
```

Preconditions:
Project must be open, timeline must exist, and each placement must provide either `clip_name` or `media_pool_path`.

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

### `timeline_build_from_paths`

Purpose:
Import media paths into the current media pool folder and create a new timeline from the imported clips in one step.

Minimum inputs:

```json
{
  "name": "Rough Cut",
  "paths": ["C:/media/clip001.mov", "C:/media/clip002.mov"]
}
```

Free-mode notes:
This is a composed workflow tool built on top of the existing low-level import and timeline creation primitives.

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

### `timeline_item_move`

Purpose:
Move one timeline item by recreating the same source range at a new position and deleting the source item.

Free-mode notes:
V1 does not promise preservation of transitions, Fusion/effects, or complex linked state.

### Animation tools

The current codebase also exposes a small v1 animation surface for video items:

- `timeline_item_properties_get`
- `timeline_item_properties_set`
- `timeline_item_animation_preset_apply`
- `timeline_item_animation_clear`
- `timeline_image_place_animated`

Animation notes:

- `timeline_item_properties_set` is a static clip-property tool, not a generic keyframe API.
- Smooth presets are Fusion-backed and currently target one video item at a time.
- `timeline_item_animation_clear` only removes DFMCP-managed Fusion comps and leaves user comps intact.
- `timeline_image_place_animated` is a composed workflow over import, placement, and preset apply.

### Additional timeline tools already implemented

The current codebase also exposes:

- `timeline_inspect`
- `timeline_track_items_list`
- `timeline_track_inspect`
- `timeline_item_inspect`
- `timeline_item_delete`
- `timeline_item_properties_get`
- `timeline_item_properties_set`
- `timeline_item_animation_preset_apply`
- `timeline_item_animation_clear`
- `timeline_image_place_animated`
- `timeline_item_split`
- `timeline_item_set_source_range`
- `timeline_gap_close`
- `timeline_remove_gaps`
- `timeline_insert_gap`

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

### Additional marker tools already implemented

The current codebase also exposes:

- `marker_inspect`
- `marker_list_range`

## Local Media-Analysis Tools

These tools do not require a live Resolve session. They run in the backend against local files, store artifacts under `runtime/analysis/<analysis_id>/`, and return structured outputs suitable for later rough-cut planning.

Currently implemented:

- `audio_probe`
- `audio_transcribe_segments`
- `audio_detect_events`
- `video_probe`
- `video_detect_shots`
- `video_sample_frames`
- `video_extract_roi_frames`
- `video_build_contact_sheet`
- `video_detect_overlay_events`
- `video_extract_segment_screenshots`
- `video_segment_from_speech`
- `video_segment_visual`
- `video_segment_audio_visual`
- `edit_plan_from_candidates`

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
- `media_pool_folder_root`
- `media_pool_folder_path`
- `media_pool_folder_list_recursive`
- `media_pool_folder_open_path`
- `media_clip_inspect`
- `media_clip_inspect_path`
- `timeline_list`
- `timeline_current`
- `timeline_create_empty`
- `timeline_set_current`
- `timeline_append_clips`
- `timeline_clips_place`
- `timeline_create_from_clips`
- `timeline_build_from_paths`
- `timeline_items_list`
- `timeline_inspect`
- `timeline_track_items_list`
- `timeline_track_inspect`
- `timeline_item_inspect`
- `timeline_item_delete`
- `timeline_item_properties_get`
- `timeline_item_properties_set`
- `timeline_item_animation_preset_apply`
- `timeline_item_animation_clear`
- `timeline_image_place_animated`
- `timeline_item_move`
- `timeline_item_split`
- `timeline_item_set_source_range`
- `timeline_gap_close`
- `timeline_remove_gaps`
- `timeline_insert_gap`
- `marker_add`
- `marker_list`
- `marker_inspect`
- `marker_list_range`
- `marker_delete`

### Local analysis primitives already available

- `audio_probe`
- `audio_transcribe_segments`
- `audio_detect_events`
- `video_probe`
- `video_detect_shots`
- `video_sample_frames`
- `video_extract_roi_frames`
- `video_build_contact_sheet`
- `video_detect_overlay_events`
- `video_extract_segment_screenshots`
- `video_segment_from_speech`
- `video_segment_visual`
- `video_segment_audio_visual`
- `edit_plan_from_candidates`

### Domain module tools already available

- `cs2_list_candidate_events`
- `cs2_build_edit_plan`

`cs2_clips` notes:

- visual-first for CS2/NVIDIA captures
- top-right kill-feed ROI is the primary signal
- lower-left cash ROI is used as a secondary local-player hint
- transcript remains a fallback when visual confidence is weak

### Composite tools for later

- apply `EditPlanProposal` automatically to a target timeline
- domain-specific candidate extraction modules that compile into shared low-level operations
- add review markers from an external metadata file

## Explicit Deferrals

- `media_browse`
- render automation breadth
- Fusion-heavy actions
- cloud/database switching
- high-level editing copilots that bypass the low-level contracts
- complex edit transforms beyond the current split/trim/gap toolset
- deep color workflows
- long-running distributed media analysis pipelines
