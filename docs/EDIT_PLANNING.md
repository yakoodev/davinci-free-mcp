# Edit Planning

## Summary

This document defines the stable machine-readable contract between media analysis results and low-level rough-cut execution.

The immediate goal is not to implement a full CS2 frag-cutter yet. The goal is to ensure the next iteration can:

1. analyze a source video
2. produce a reviewable cut proposal
3. compile that proposal into known low-level Resolve tools
4. apply the cut on a target timeline

## Canonical Contract

Use `EditPlanProposal` as the wire contract for a proposed cut.

Fields:

- `source_path`
  Original media file being analyzed.
- `target_timeline_name`
  Timeline that should receive the rough cut.
- `summary`
  Short human-readable explanation of why the proposed cut exists.
- `segments`
  Candidate source segments with labels, optional scores, and transcript hints.
- `operations`
  Ordered low-level tool calls that can be executed deterministically.
- `warnings`
  Any uncertainty or live-verification notes.

Each operation is an `EditPlanOperation`:

- `tool_name`
  One of:
  - `timeline_clips_place`
  - `timeline_item_split`
  - `timeline_item_set_source_range`
  - `timeline_gap_close`
  - `timeline_remove_gaps`
  - `timeline_insert_gap`
- `timeline_name`
  Optional explicit target timeline.
- `arguments`
  Exact low-level tool payload.
- `source_segment`
  Optional link back to the analyzed source segment that motivated the operation.

## Analysis Inputs

The next planner iteration should build proposals from existing analysis tools, not from ad hoc parsing:

- `audio_transcribe_segments`
  Speech-driven timing hints and per-track transcript context.
- `video_detect_shots`
  Visual cut boundaries and shot candidates.
- `video_segment_from_speech`
  Speech-based clip suggestions.
- `video_segment_audio_visual`
  Combined audio/visual segment candidates for impact-heavy footage.

Preferred aggregation rule:

- analysis tools produce segment candidates
- planner ranks and merges candidates
- planner emits one `EditPlanProposal`
- execution layer applies `operations` in order

## Execution Mapping

Preferred compilation model:

- `timeline_clips_place`
  Initial placement of selected source clips on a new or dedicated rough-cut timeline.
- `timeline_item_split`
  Split placed items on edit points derived from proposal segments.
- `timeline_item_set_source_range`
  Trim each placed timeline item to the proposed source bounds.
- `timeline_gap_close`
  Close local gaps after removing unwanted tails.
- `timeline_remove_gaps`
  Compact the final rough cut on a track.
- `timeline_insert_gap`
  Reserve breathing room for commentary, transitions, or later inserts.

## Future CS2 Flow

The intended next scenario is:

1. input `.mp4` or `.mkv` gameplay capture
2. analyze likely frag moments with audio and visual segmentation
3. show the user a proposal with timestamps, labels, and confidence
4. after approval, create/apply the rough cut in DaVinci
5. verify the resulting timeline with `timeline_items_list` and `timeline_inspect`

For CS2 frag cutting specifically, likely candidate signals are:

- impact or high-energy audio events
- speech bursts around reactions/callouts
- scene changes or high-motion windows around kills

The planner should still output generic `EditPlanProposal` data rather than a CS2-specific schema.
