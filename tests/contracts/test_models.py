from davinci_free_mcp.contracts import (
    AudioEventsData,
    AudioProbeData,
    AudioTranscriptionData,
    TranscriptSidecarData,
    BridgeCommand,
    BridgeResult,
    VideoSegmentationData,
    VideoShotsData,
    ResolveMarkerInspectData,
    ResolveMarkerRangeListData,
    ResolveMediaClipInspectPathData,
    ResolveMediaPoolFolderRecursiveData,
    ResolveMediaPoolFolderStateData,
    ResolveProjectManagerFolderStateData,
    ResolveTimelineClipsPlaceData,
    ResolveTimelineBuildFromPathsData,
    ResolveTimelineInspectData,
    ResolveTimelineItemDeleteData,
    ResolveTimelineItemInspectData,
    ResolveTimelineItemMoveData,
    ResolveTimelineTrackInspectData,
    ResolveTimelineTrackItemsData,
)


def test_bridge_command_round_trip() -> None:
    command = BridgeCommand(
        command="resolve_health",
        target={"project": "Demo"},
        payload={"sample": True},
        timeout_ms=1234,
        context={"caller": "test"},
    )

    restored = BridgeCommand.model_validate(command.model_dump(mode="json"))

    assert restored.command == "resolve_health"
    assert restored.target["project"] == "Demo"
    assert restored.payload["sample"] is True
    assert restored.timeout_ms == 1234


def test_bridge_result_failure_preserves_category() -> None:
    result = BridgeResult.failure(
        "req-1",
        "timeout",
        "Executor did not respond in time.",
        details={"timeout_ms": 50},
    )

    restored = BridgeResult.model_validate(result.model_dump(mode="json"))

    assert restored.ok is False
    assert restored.error is not None
    assert restored.error.category == "timeout"
    assert restored.error.details["timeout_ms"] == 50


def test_media_pool_folder_state_data_round_trip() -> None:
    payload = ResolveMediaPoolFolderStateData.model_validate(
        {
            "folder": {"name": "Closeups"},
            "path": [{"name": "Master"}, {"name": "Selects"}, {"name": "Closeups"}],
            "subfolders": [{"name": "Alt"}],
            "clips": [{"name": "clip001.mov"}],
        }
    )

    restored = ResolveMediaPoolFolderStateData.model_validate(payload.model_dump(mode="json"))

    assert restored.path[1].name == "Selects"
    assert restored.clips[0].name == "clip001.mov"


def test_project_manager_folder_state_data_round_trip() -> None:
    payload = ResolveProjectManagerFolderStateData.model_validate(
        {
            "folder": {"name": "Commercials"},
            "path": [{"name": "Root"}, {"name": "Clients"}, {"name": "Commercials"}],
            "subfolders": [{"name": "2026"}],
            "projects": [{"name": "Spot A"}],
        }
    )

    restored = ResolveProjectManagerFolderStateData.model_validate(
        payload.model_dump(mode="json")
    )

    assert restored.path[1].name == "Clients"
    assert restored.projects[0].name == "Spot A"


def test_timeline_inspect_data_round_trip() -> None:
    payload = ResolveTimelineInspectData.model_validate(
        {
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 2, "name": "Review"},
            "video_track_count": 2,
            "audio_track_count": 1,
            "video_item_count": 5,
            "audio_item_count": 3,
            "marker_count": 4,
        }
    )

    restored = ResolveTimelineInspectData.model_validate(payload.model_dump(mode="json"))

    assert restored.timeline.name == "Review"
    assert restored.marker_count == 4


def test_timeline_track_items_data_round_trip() -> None:
    payload = ResolveTimelineTrackItemsData.model_validate(
        {
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 1, "name": "Assembly"},
            "track": {
                "track_type": "video",
                "track_index": 2,
                "items": [{"item_index": 0, "name": "clip001.mov", "start_frame": 0, "end_frame": 100}],
            },
        }
    )

    restored = ResolveTimelineTrackItemsData.model_validate(payload.model_dump(mode="json"))

    assert restored.track.track_index == 2
    assert restored.track.items[0].name == "clip001.mov"


def test_marker_inspect_data_round_trip() -> None:
    payload = ResolveMarkerInspectData.model_validate(
        {
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 1, "name": "Assembly"},
            "marker": {"frame": 24, "name": "Review", "color": "Blue", "duration": 1},
        }
    )

    restored = ResolveMarkerInspectData.model_validate(payload.model_dump(mode="json"))

    assert restored.marker.frame == 24
    assert restored.marker.name == "Review"


def test_media_clip_inspect_path_data_round_trip() -> None:
    payload = ResolveMediaClipInspectPathData.model_validate(
        {
            "folder": {"name": "Closeups"},
            "path": [{"name": "Master"}, {"name": "Selects"}, {"name": "Closeups"}],
            "clip": {"name": "clip001.mov", "properties": {"File Path": "C:/media/clip001.mov"}},
        }
    )

    restored = ResolveMediaClipInspectPathData.model_validate(payload.model_dump(mode="json"))

    assert restored.path[-1].name == "Closeups"
    assert restored.clip.properties["File Path"] == "C:/media/clip001.mov"


def test_media_pool_folder_recursive_data_round_trip() -> None:
    payload = ResolveMediaPoolFolderRecursiveData.model_validate(
        {
            "folder": {"name": "Master"},
            "path": [{"name": "Master"}],
            "max_depth": 2,
            "tree": {
                "name": "Master",
                "clips": [{"name": "root.mov"}],
                "subfolders": [{"name": "Selects", "clips": [], "subfolders": []}],
            },
        }
    )

    restored = ResolveMediaPoolFolderRecursiveData.model_validate(payload.model_dump(mode="json"))

    assert restored.tree.subfolders[0].name == "Selects"
    assert restored.max_depth == 2


def test_timeline_track_inspect_data_round_trip() -> None:
    payload = ResolveTimelineTrackInspectData.model_validate(
        {
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 1, "name": "Assembly"},
            "track_type": "video",
            "track_index": 1,
            "item_count": 2,
            "start_frame": 0,
            "end_frame": 200,
        }
    )

    restored = ResolveTimelineTrackInspectData.model_validate(payload.model_dump(mode="json"))

    assert restored.item_count == 2
    assert restored.end_frame == 200


def test_marker_range_list_data_round_trip() -> None:
    payload = ResolveMarkerRangeListData.model_validate(
        {
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 1, "name": "Assembly"},
            "frame_from": 10,
            "frame_to": 20,
            "markers": [{"frame": 12, "name": "A"}],
        }
    )

    restored = ResolveMarkerRangeListData.model_validate(payload.model_dump(mode="json"))

    assert restored.frame_from == 10
    assert restored.markers[0].frame == 12


def test_timeline_item_inspect_data_round_trip() -> None:
    payload = ResolveTimelineItemInspectData.model_validate(
        {
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 1, "name": "Assembly"},
            "item": {
                "item_index": 0,
                "name": "clip001.mov",
                "track_type": "video",
                "track_index": 1,
                "start_frame": 100,
                "end_frame": 124,
            },
            "duration": 24,
            "source_start_frame": 0,
            "source_end_frame": 24,
            "left_offset": 0,
            "right_offset": 0,
        }
    )

    restored = ResolveTimelineItemInspectData.model_validate(payload.model_dump(mode="json"))

    assert restored.item.name == "clip001.mov"
    assert restored.duration == 24


def test_timeline_clips_place_data_round_trip() -> None:
    payload = ResolveTimelineClipsPlaceData.model_validate(
        {
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 1, "name": "Assembly"},
            "placed_count": 1,
            "items": [
                {
                    "item_index": 0,
                    "name": "clip001.mov",
                    "track_type": "video",
                    "track_index": 1,
                    "start_frame": 100,
                    "end_frame": 124,
                }
            ],
        }
    )

    restored = ResolveTimelineClipsPlaceData.model_validate(payload.model_dump(mode="json"))

    assert restored.placed_count == 1
    assert restored.items[0].track_type == "video"


def test_timeline_build_from_paths_data_round_trip() -> None:
    payload = ResolveTimelineBuildFromPathsData.model_validate(
        {
            "created": True,
            "timeline": {"index": 2, "name": "Rough Cut"},
            "imported_count": 2,
            "count": 2,
            "paths": ["C:/media/a.mov", "C:/media/b.mov"],
            "clip_names": ["a.mov", "b.mov"],
        }
    )

    restored = ResolveTimelineBuildFromPathsData.model_validate(payload.model_dump(mode="json"))

    assert restored.created is True
    assert restored.imported_count == 2
    assert restored.clip_names[1] == "b.mov"


def test_timeline_item_delete_data_round_trip() -> None:
    payload = ResolveTimelineItemDeleteData.model_validate(
        {
            "deleted": True,
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 1, "name": "Assembly"},
            "item": {
                "item_index": 0,
                "name": "clip001.mov",
                "track_type": "video",
                "track_index": 1,
                "start_frame": 100,
                "end_frame": 124,
            },
            "ripple": False,
        }
    )

    restored = ResolveTimelineItemDeleteData.model_validate(payload.model_dump(mode="json"))

    assert restored.deleted is True
    assert restored.item.item_index == 0


def test_timeline_item_move_data_round_trip() -> None:
    payload = ResolveTimelineItemMoveData.model_validate(
        {
            "moved": True,
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 1, "name": "Assembly"},
            "source_item": {
                "item_index": 0,
                "name": "clip001.mov",
                "track_type": "video",
                "track_index": 1,
                "start_frame": 100,
                "end_frame": 124,
            },
            "item": {
                "item_index": 1,
                "name": "clip001.mov",
                "track_type": "video",
                "track_index": 2,
                "start_frame": 200,
                "end_frame": 224,
            },
        }
    )

    restored = ResolveTimelineItemMoveData.model_validate(payload.model_dump(mode="json"))

    assert restored.moved is True
    assert restored.source_item.track_index == 1
    assert restored.item.track_index == 2


def test_audio_probe_data_round_trip() -> None:
    payload = AudioProbeData.model_validate(
        {
            "source": "C:/media/test.wav",
            "analysis_id": "abc123",
            "artifacts_dir": "C:/runtime/analysis/abc123",
            "media": {
                "duration_sec": 3.5,
                "sample_rate": 48000,
                "channels": 2,
                "codec": "pcm",
                "bit_rate": 1536000,
            },
            "audio": {
                "has_audio": True,
                "speech_likelihood": 0.8,
                "silence_ratio": 0.1,
            },
            "artifacts": [{"kind": "json", "path": "C:/runtime/analysis/abc123/manifest.json", "label": "manifest"}],
        }
    )

    restored = AudioProbeData.model_validate(payload.model_dump(mode="json"))

    assert restored.media.sample_rate == 48000
    assert restored.audio.has_audio is True


def test_audio_transcription_data_round_trip() -> None:
    payload = AudioTranscriptionData.model_validate(
        {
            "source": "C:/media/test.wav",
            "analysis_id": "abc123",
            "artifacts_dir": "C:/runtime/analysis/abc123",
            "transcript_status": "no_speech_detected",
            "segments": [],
            "artifacts": [{"kind": "text", "path": "C:/runtime/analysis/abc123/transcript.txt", "label": "transcript_text"}],
        }
    )

    restored = AudioTranscriptionData.model_validate(payload.model_dump(mode="json"))

    assert restored.transcript_status == "no_speech_detected"
    assert restored.segments == []


def test_audio_events_data_round_trip() -> None:
    payload = AudioEventsData.model_validate(
        {
            "source": "C:/media/test.wav",
            "analysis_id": "abc123",
            "artifacts_dir": "C:/runtime/analysis/abc123",
            "summary": {
                "speech_detected": False,
                "music_detected": True,
                "silence_ranges_count": 1,
            },
            "events": [
                {
                    "start": 0.0,
                    "end": 1.0,
                    "event_type": "music_like",
                    "energy": 1200.0,
                    "label": "Music-like segment",
                }
            ],
            "artifacts": [{"kind": "json", "path": "C:/runtime/analysis/abc123/events.json", "label": "events"}],
        }
    )

    restored = AudioEventsData.model_validate(payload.model_dump(mode="json"))

    assert restored.summary.music_detected is True
    assert restored.events[0].event_type == "music_like"


def test_video_shots_data_round_trip() -> None:
    payload = VideoShotsData.model_validate(
        {
            "source": "C:/media/test.mp4",
            "analysis_id": "abc123",
            "artifacts_dir": "C:/runtime/analysis/abc123",
            "shots": [
                {
                    "shot_index": 0,
                    "start": 0.0,
                    "end": 2.0,
                    "segment_source": "scene",
                    "visual_features": {
                        "scene_change": True,
                        "motion_score": 0.2,
                        "black_frame_ratio": 0.0,
                    },
                }
            ],
            "artifacts": [{"kind": "json", "path": "C:/runtime/analysis/abc123/segments.json", "label": "shots"}],
        }
    )

    restored = VideoShotsData.model_validate(payload.model_dump(mode="json"))

    assert restored.shots[0].segment_source == "scene"
    assert restored.shots[0].visual_features.motion_score == 0.2


def test_video_segmentation_data_round_trip() -> None:
    payload = VideoSegmentationData.model_validate(
        {
            "source": "C:/media/test.mp4",
            "analysis_id": "abc123",
            "artifacts_dir": "C:/runtime/analysis/abc123",
            "segmentation_mode": "audio_visual",
            "segments": [
                {
                    "segment_index": 0,
                    "start": 1.0,
                    "end": 3.0,
                    "segment_source": "audio_event",
                    "transcript": None,
                    "audio_event": "music_like",
                    "audio_features": {
                        "speech_detected": False,
                        "music_detected": True,
                        "silence": False,
                        "energy": 0.7,
                    },
                    "visual_features": {
                        "scene_change": True,
                        "motion_score": 0.4,
                        "black_frame_ratio": 0.0,
                    },
                    "source_track_indexes": [1],
                    "screenshots": [
                        {
                            "path": "C:/runtime/analysis/abc123/screenshots/1.jpg",
                            "timestamp_sec": 2.0,
                            "kind": "midpoint",
                        }
                    ],
                }
            ],
            "artifacts": [{"kind": "json", "path": "C:/runtime/analysis/abc123/segments.json", "label": "segments"}],
        }
    )

    restored = VideoSegmentationData.model_validate(payload.model_dump(mode="json"))

    assert restored.segmentation_mode == "audio_visual"
    assert restored.segments[0].audio_event == "music_like"


def test_transcript_sidecar_data_round_trip() -> None:
    payload = TranscriptSidecarData.model_validate(
        {
            "source": "C:/media/test.mp4",
            "created_at": "2026-03-13T16:20:00Z",
            "engine": {
                "name": "faster-whisper",
                "model": "base",
                "device": "cpu",
                "compute_type": "int8",
            },
            "language": "ru",
            "duration_sec": 101.4,
            "transcript_status": "ok",
            "segments": [
                {
                    "start": 0.5,
                    "end": 1.5,
                    "text": "пример",
                    "confidence": 0.87,
                    "track_index": 1,
                }
            ],
        }
    )

    restored = TranscriptSidecarData.model_validate(payload.model_dump(mode="json"))

    assert restored.engine.name == "faster-whisper"
    assert restored.segments[0].text == "пример"
    assert restored.segments[0].track_index == 1
