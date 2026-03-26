import json
import math
import struct
import sys
import types
import wave
from pathlib import Path

import pytest

from davinci_free_mcp.backend import ResolveBackendService
from davinci_free_mcp.bridge.base import Bridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import BridgeCommand, BridgeResult


class FakeBridge(Bridge):
    def __init__(self, result: BridgeResult) -> None:
        self._result = result

    def submit_command(self, command: BridgeCommand) -> str:
        return command.request_id

    def await_result(self, request_id: str, timeout_ms: int) -> BridgeResult:
        return self._result.model_copy(update={"request_id": request_id})

    def health_check(self) -> dict[str, object]:
        return {"available": True, "adapter": "fake"}


class SequenceBridge(Bridge):
    def __init__(self, results: list[BridgeResult]) -> None:
        self._results = list(results)
        self.commands: list[BridgeCommand] = []

    def submit_command(self, command: BridgeCommand) -> str:
        self.commands.append(command)
        return command.request_id

    def await_result(self, request_id: str, timeout_ms: int) -> BridgeResult:
        result = self._results.pop(0)
        return result.model_copy(update={"request_id": request_id})

    def health_check(self) -> dict[str, object]:
        return {"available": True, "adapter": "sequence"}


def _write_wav(path: Path, amplitudes: list[int], frame_rate: int = 8000) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(frame_rate)
        frames = b"".join(struct.pack("<h", amplitude) for amplitude in amplitudes)
        wav_file.writeframes(frames)


def _install_fake_faster_whisper(
    monkeypatch: pytest.MonkeyPatch,
    *,
    segments: list[dict[str, object]],
    language: str = "ru",
    calls: list[dict[str, object]] | None = None,
) -> None:
    class FakeSegment:
        def __init__(self, start: float, end: float, text: str, confidence: float | None = None) -> None:
            self.start = start
            self.end = end
            self.text = text
            self.avg_logprob = confidence

    class FakeInfo:
        def __init__(self, language_value: str) -> None:
            self.language = language_value

    class FakeWhisperModel:
        def __init__(self, model: str, device: str = "cpu", compute_type: str = "int8") -> None:
            if calls is not None:
                calls.append({"event": "init", "model": model, "device": device, "compute_type": compute_type})

        def transcribe(self, audio_path: str, language: str | None = None, beam_size: int = 1):
            if calls is not None:
                calls.append({"event": "transcribe", "audio_path": audio_path, "language": language, "beam_size": beam_size})
            return (
                [FakeSegment(**segment) for segment in segments],
                FakeInfo(language or "ru"),
            )

    fake_module = types.SimpleNamespace(WhisperModel=FakeWhisperModel)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)


def _multi_track_sidecar_payload(video_path: Path) -> dict[str, object]:
    return {
        "source": str(video_path),
        "created_at": "2026-03-13T16:20:00Z",
        "engine": {
            "name": "faster-whisper",
            "model": "base",
            "device": "cpu",
            "compute_type": "int8",
        },
        "language": "en",
        "duration_sec": 8.0,
        "transcript_status": "ok",
        "segments": [
            {"start": 0.0, "end": 2.0, "text": "one", "confidence": 0.7, "track_index": 1},
            {"start": 2.1, "end": 4.0, "text": "two", "confidence": 0.9, "track_index": 1},
        ],
    }


def test_marker_add_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "added": True,
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "marker": {
                        "frame": "not-an-int",
                        "color": "Blue",
                        "name": "Review",
                        "duration": 1,
                    },
                },
            )
        ),
        AppSettings(),
    )

    result = service.marker_add(10, "Review")

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_marker_list_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "markers": [{"frame": "bad"}],
                },
            )
        ),
        AppSettings(),
    )

    result = service.marker_list()

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_media_clip_inspect_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "folder": {"name": "Master"},
                    "clip": {"name": "clip001.mov", "properties": ["bad"]},
                },
            )
        ),
        AppSettings(),
    )

    result = service.media_clip_inspect("clip001.mov")

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_create_from_clips_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "created": True,
                    "timeline": {"index": 1, "name": "Assembly"},
                    "count": "bad",
                    "clip_names": ["clip001.mov"],
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_create_from_clips("Assembly", ["clip001.mov"])

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_build_from_paths_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "created": True,
                    "timeline": {"index": 1, "name": "Assembly"},
                    "imported_count": 2,
                    "count": 2,
                    "paths": ["C:/media/clip001.mov"],
                    "clip_names": "bad",
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_build_from_paths("Assembly", ["C:/media/clip001.mov"])

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_inspect_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "video_track_count": "bad",
                    "audio_track_count": 1,
                    "video_item_count": 2,
                    "audio_item_count": 0,
                    "marker_count": 3,
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_inspect()

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_track_items_list_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "track": {"track_type": "video", "track_index": "bad", "items": []},
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_track_items_list("video", 1)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_project_manager_folder_path_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "folder": {"name": "Clients"},
                    "path": [{"name": "Root"}, {"name": 123}],
                    "subfolders": [],
                    "projects": [],
                },
            )
        ),
        AppSettings(),
    )

    result = service.project_manager_folder_path()

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_marker_inspect_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "marker": {"frame": "bad"},
                },
            )
        ),
        AppSettings(),
    )

    result = service.marker_inspect(10)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_track_inspect_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "track_type": "video",
                    "track_index": 1,
                    "item_count": "bad",
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_track_inspect("video", 1)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_marker_list_range_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "frame_from": 10,
                    "frame_to": 20,
                    "markers": [{"frame": "bad"}],
                },
            )
        ),
        AppSettings(),
    )

    result = service.marker_list_range(10, 20)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_item_inspect_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "item": {
                        "item_index": 0,
                        "name": "clip001.mov",
                        "track_type": "video",
                        "track_index": 1,
                        "start_frame": "bad",
                    },
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_item_inspect("video", 1, 0)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_item_move_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
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
                        "track_index": "bad",
                        "start_frame": 200,
                        "end_frame": 224,
                    },
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_item_move("video", 1, 0, 200)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_item_properties_get_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
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
                    "properties": [],
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_item_properties_get("video", 1, 0)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_item_properties_set_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "updated": True,
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
                    "properties": "bad",
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_item_properties_set("video", 1, 0, {"Opacity": 80})

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_item_animation_preset_apply_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "applied": True,
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
                    "applied_preset": "fade_in",
                    "fusion_comp_name": "DFMCP Anim",
                    "properties": "bad",
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_item_animation_preset_apply("video", 1, 0, "fade_in")

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_image_place_animated_orchestrates_import_place_and_animation() -> None:
    bridge = SequenceBridge(
        [
            BridgeResult.success(
                "req-1",
                data={"imported_count": 1, "items": [{"name": "image.png"}]},
            ),
            BridgeResult.success(
                "req-2",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "placed_count": 1,
                    "items": [
                        {
                            "item_index": None,
                            "name": "image.png",
                            "track_type": "video",
                            "track_index": 2,
                            "start_frame": 100,
                            "end_frame": 140,
                        }
                    ],
                },
            ),
            BridgeResult.success(
                "req-3",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "track": {
                        "track_type": "video",
                        "track_index": 2,
                        "items": [
                            {
                                "item_index": 3,
                                "name": "image.png",
                                "start_frame": 100,
                                "end_frame": 140,
                            }
                        ],
                    },
                },
            ),
            BridgeResult.success(
                "req-4",
                data={
                    "updated": True,
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "item": {
                        "item_index": 3,
                        "name": "image.png",
                        "track_type": "video",
                        "track_index": 2,
                        "start_frame": 100,
                        "end_frame": 140,
                    },
                    "properties": {"Opacity": 80.0, "ZoomX": 1.1, "ZoomY": 1.1},
                },
            ),
            BridgeResult.success(
                "req-5",
                data={
                    "applied": True,
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "item": {
                        "item_index": 3,
                        "name": "image.png",
                        "track_type": "video",
                        "track_index": 2,
                        "start_frame": 100,
                        "end_frame": 140,
                    },
                    "applied_preset": "fade_in",
                    "fusion_comp_name": "DFMCP Anim",
                    "properties": {"Opacity": 80.0, "ZoomX": 1.1, "ZoomY": 1.1},
                },
            ),
        ]
    )
    service = ResolveBackendService(bridge, AppSettings())

    result = service.timeline_image_place_animated(
        "C:/media/image.png",
        100,
        2,
        40,
        "fade_in",
        opacity=80.0,
        scale=1.1,
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["imported_count"] == 1
    assert result.data["item"]["item_index"] == 3
    assert result.data["applied_preset"] == "fade_in"
    assert [command.command for command in bridge.commands] == [
        "media_import",
        "timeline_clips_place",
        "timeline_track_items_list",
        "timeline_item_properties_set",
        "timeline_item_animation_preset_apply",
    ]


def test_timeline_item_split_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "split_frame": 130,
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "left_item": {
                        "item_index": 0,
                        "name": "clip001.mov",
                        "track_type": "video",
                        "track_index": 1,
                        "start_frame": 100,
                        "end_frame": 130,
                    },
                    "right_item": {
                        "item_index": 1,
                        "name": "clip001.mov",
                        "track_type": "video",
                        "track_index": "bad",
                        "start_frame": 130,
                        "end_frame": 160,
                    },
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_item_split("video", 1, 0, 130)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_item_set_source_range_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "updated": True,
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
                        "item_index": 0,
                        "name": "clip001.mov",
                        "track_type": "video",
                        "track_index": 1,
                        "start_frame": "bad",
                        "end_frame": 130,
                    },
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_item_set_source_range("video", 1, 0, 10, 40)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_gap_close_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "closed": True,
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "track_type": "video",
                    "track_index": 1,
                    "frame_from": 50,
                    "frame_to": 80,
                    "shifted_item_count": "bad",
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_gap_close("video", 1, 50)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_remove_gaps_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "removed_gap_count": 2,
                    "shifted_item_count": 2,
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "track_type": "video",
                    "track_index": "bad",
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_remove_gaps("video", 1)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_insert_gap_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "inserted": True,
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "track_type": "video",
                    "track_index": 1,
                    "at_frame": 50,
                    "duration": "bad",
                    "shifted_item_count": 1,
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_insert_gap("video", 1, 50, 20)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_audio_transcribe_segments_creates_sidecar_on_first_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wav_path = tmp_path / "speech.wav"
    _write_wav(wav_path, [0] * 8000)
    calls: list[dict[str, object]] = []
    _install_fake_faster_whisper(
        monkeypatch,
        segments=[{"start": 0.0, "end": 1.0, "text": "hello", "confidence": 0.7}],
        calls=calls,
    )
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.audio_transcribe_segments(str(wav_path))

    assert result.success is True
    assert result.data is not None
    assert result.data["transcript_status"] == "ok"
    assert len(result.data["segments"]) == 1
    assert result.data["segments"][0]["track_index"] == 0
    sidecar_path = wav_path.with_name("speech.wav.transcript.json")
    assert sidecar_path.exists()
    assert any(item["event"] == "transcribe" for item in calls)


def test_audio_transcribe_segments_reuses_existing_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wav_path = tmp_path / "speech.wav"
    _write_wav(wav_path, [0] * 8000)
    calls: list[dict[str, object]] = []
    _install_fake_faster_whisper(
        monkeypatch,
        segments=[{"start": 0.0, "end": 1.0, "text": "hello", "confidence": 0.7}],
        calls=calls,
    )
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    first = service.audio_transcribe_segments(str(wav_path))
    second = service.audio_transcribe_segments(str(wav_path))

    assert first.success is True
    assert second.success is True
    assert len([item for item in calls if item["event"] == "transcribe"]) == 1


def test_audio_transcribe_segments_rebuilds_invalid_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wav_path = tmp_path / "speech.wav"
    _write_wav(wav_path, [0] * 8000)
    wav_path.with_name("speech.wav.transcript.json").write_text("{bad json", encoding="utf-8")
    calls: list[dict[str, object]] = []
    _install_fake_faster_whisper(
        monkeypatch,
        segments=[{"start": 0.0, "end": 1.0, "text": "hello", "confidence": 0.7}],
        calls=calls,
    )
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.audio_transcribe_segments(str(wav_path))

    assert result.success is True
    assert len([item for item in calls if item["event"] == "transcribe"]) == 1


def test_audio_transcribe_segments_returns_no_speech_after_successful_transcription(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wav_path = tmp_path / "speech.wav"
    _write_wav(wav_path, [0] * 8000)
    _install_fake_faster_whisper(monkeypatch, segments=[])
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.audio_transcribe_segments(str(wav_path))

    assert result.success is True
    assert result.data is not None
    assert result.data["transcript_status"] == "no_speech_detected"
    assert result.data["segments"] == []
    assert result.warnings


def test_audio_transcribe_segments_returns_execution_failure_when_faster_whisper_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wav_path = tmp_path / "speech.wav"
    _write_wav(wav_path, [0] * 8000)
    import davinci_free_mcp.backend.media_analysis as media_analysis_module

    monkeypatch.delitem(sys.modules, "faster_whisper", raising=False)
    monkeypatch.setattr(
        media_analysis_module.importlib,
        "import_module",
        lambda name: (_ for _ in ()).throw(ImportError("missing")),
    )
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.audio_transcribe_segments(str(wav_path))

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_video_segment_from_speech_uses_transcript_sidecar_and_creates_screenshots(tmp_path: Path) -> None:
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"fake-video")
    probe_sidecar = video_path.with_name("clip.mp4.probe.json")
    probe_sidecar.write_text(json.dumps({"duration_sec": 8.0, "video_codec": "h264", "audio_codec": "aac"}), encoding="utf-8")
    transcript_sidecar = video_path.with_name("clip.mp4.transcript.json")
    transcript_sidecar.write_text(
        json.dumps(_multi_track_sidecar_payload(video_path)),
        encoding="utf-8",
    )
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.video_segment_from_speech(str(video_path), max_segment_sec=10)

    assert result.success is True
    assert result.data is not None
    assert result.data["transcript_status"] == "ok"
    assert len(result.data["segments"]) == 1
    assert result.data["segments"][0]["track_index"] == 1
    assert Path(result.data["segments"][0]["screenshot_path"]).exists()
    assert (tmp_path / "runtime" / "analysis" / result.data["analysis_id"] / "transcript.json").exists()


def test_video_segment_from_speech_creates_sidecar_for_mp4(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"fake-video")
    wav_path = tmp_path / "transcription.wav"
    _write_wav(wav_path, [0] * 4000)
    video_path.with_name("clip.mp4.probe.json").write_text(
        json.dumps({"duration_sec": 8.0, "video_codec": "h264", "audio_codec": "aac"}),
        encoding="utf-8",
    )
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )
    monkeypatch.setattr(
        service.media_analyzer,
        "list_audio_streams",
        lambda source: [{"stream_index": 1, "codec_name": "aac", "language": None, "title": None}],
    )
    monkeypatch.setattr(
        service.media_analyzer,
        "_extract_audio_for_transcription",
        lambda source, stream_index=None: (wav_path, None),
    )
    monkeypatch.setattr(
        service.media_analyzer,
        "_transcribe_with_faster_whisper",
        lambda audio_path, language=None: (
            [{"start": 0.0, "end": 1.5, "text": "frag", "confidence": 0.8}],
            "ru",
        ),
    )

    result = service.video_segment_from_speech(str(video_path))

    assert result.success is True
    assert result.data is not None
    assert result.data["transcript_status"] == "ok"
    assert video_path.with_name("clip.mp4.transcript.json").exists()
    payload = json.loads(video_path.with_name("clip.mp4.transcript.json").read_text(encoding="utf-8"))
    assert payload["segments"][0]["track_index"] == 1


def test_video_segment_from_speech_keeps_tracks_separate_when_merging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"fake-video")
    wav_path = tmp_path / "transcription.wav"
    _write_wav(wav_path, [0] * 4000)
    video_path.with_name("clip.mp4.probe.json").write_text(
        json.dumps({"duration_sec": 8.0, "video_codec": "h264", "audio_codec": "aac"}),
        encoding="utf-8",
    )
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )
    monkeypatch.setattr(
        service.media_analyzer,
        "list_audio_streams",
        lambda source: [
            {"stream_index": 1, "codec_name": "aac", "language": None, "title": None, "start_time": 0.0},
            {"stream_index": 2, "codec_name": "aac", "language": None, "title": None, "start_time": 0.004},
        ],
    )
    monkeypatch.setattr(
        service.media_analyzer,
        "_extract_audio_for_transcription",
        lambda source, stream_index=None: (wav_path, None),
    )

    def _fake_transcribe(audio_path, language=None):
        if not hasattr(_fake_transcribe, "count"):
            _fake_transcribe.count = 0
        _fake_transcribe.count += 1
        if _fake_transcribe.count == 1:
            return ([{"start": 5.0, "end": 6.0, "text": "one", "confidence": 0.8}], "ru")
        return ([{"start": 1.1, "end": 2.0, "text": "two", "confidence": 0.9}], "ru")

    monkeypatch.setattr(service.media_analyzer, "_transcribe_with_faster_whisper", _fake_transcribe)

    result = service.video_segment_from_speech(str(video_path), max_segment_sec=10)

    assert result.success is True
    assert result.data is not None
    assert len(result.data["segments"]) == 2
    assert result.data["segments"][0]["text"] == "two"
    assert result.data["segments"][1]["text"] == "one"
    assert result.data["segments"][0]["track_index"] == 2
    assert result.data["segments"][1]["track_index"] == 1
    payload = json.loads(video_path.with_name("clip.mp4.transcript.json").read_text(encoding="utf-8"))
    assert [segment["track_index"] for segment in payload["segments"]] == [2, 1]
    assert [segment["text"] for segment in payload["segments"]] == ["two", "one"]
    assert payload["segments"][0]["start"] == 1.104
    assert payload["segments"][0]["end"] == 2.004


def test_audio_transcribe_segments_keeps_single_file_timestamps_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wav_path = tmp_path / "speech.wav"
    _write_wav(wav_path, [0] * 8000)
    _install_fake_faster_whisper(
        monkeypatch,
        segments=[{"start": 0.25, "end": 1.5, "text": "hello", "confidence": 0.7}],
    )
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.audio_transcribe_segments(str(wav_path))

    assert result.success is True
    assert result.data is not None
    assert result.data["segments"][0]["start"] == 0.25
    assert result.data["segments"][0]["end"] == 1.5
    payload = json.loads(wav_path.with_name("speech.wav.transcript.json").read_text(encoding="utf-8"))
    assert payload["segments"][0]["start"] == 0.25
    assert payload["segments"][0]["end"] == 1.5


def test_video_segment_visual_returns_scene_segments_from_shots_sidecar(tmp_path: Path) -> None:
    video_path = tmp_path / "silent.mp4"
    video_path.write_bytes(b"fake-video")
    video_path.with_name("silent.mp4.probe.json").write_text(
        json.dumps({"duration_sec": 6.0, "video_codec": "h264"}),
        encoding="utf-8",
    )
    video_path.with_name("silent.mp4.shots.json").write_text(
        json.dumps(
            {
                "shots": [
                    {"start": 0.0, "end": 2.0, "motion_score": 0.1, "black_frame_ratio": 0.0, "scene_change": True},
                    {"start": 2.0, "end": 6.0, "motion_score": 0.3, "black_frame_ratio": 0.0, "scene_change": True},
                ]
            }
        ),
        encoding="utf-8",
    )
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.video_segment_visual(str(video_path))

    assert result.success is True
    assert result.data is not None
    assert result.data["segmentation_mode"] == "visual"
    assert result.data["segments"][0]["segment_source"] == "scene"


def test_video_segment_audio_visual_uses_audio_events(tmp_path: Path) -> None:
    video_path = tmp_path / "music.mp4"
    video_path.write_bytes(b"fake-video")
    video_path.with_name("music.mp4.probe.json").write_text(
        json.dumps({"duration_sec": 5.0, "video_codec": "h264", "audio_codec": "aac"}),
        encoding="utf-8",
    )
    video_path.with_name("music.mp4.events.json").write_text(
        json.dumps(
            {
                "summary": {"speech_detected": False, "music_detected": True, "silence_ranges_count": 0},
                "events": [
                    {"start": 0.5, "end": 3.0, "event_type": "music_like", "energy": 1400.0, "label": "Music-like segment"}
                ],
            }
        ),
        encoding="utf-8",
    )
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.video_segment_audio_visual(str(video_path))

    assert result.success is True
    assert result.data is not None
    assert result.data["segmentation_mode"] == "audio_visual"
    assert result.data["segments"][0]["audio_event"] == "music_like"
    assert result.data["segments"][0]["start"] == 0.5
    assert result.data["segments"][0]["end"] == 3.0


def test_video_segment_visual_validates_segment_mode(tmp_path: Path) -> None:
    video_path = tmp_path / "silent.mp4"
    video_path.write_bytes(b"fake-video")
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.video_segment_visual(str(video_path), segment_mode="bad")

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_video_extract_segment_screenshots_validates_positive_count(tmp_path: Path) -> None:
    video_path = tmp_path / "silent.mp4"
    video_path.write_bytes(b"fake-video")
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.video_extract_segment_screenshots(
        str(video_path),
        segments=[{"start": 0.0, "end": 1.0}],
        screenshots_per_segment=0,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_audio_detect_events_returns_events_for_wav(tmp_path: Path) -> None:
    wav_path = tmp_path / "events.wav"
    _write_wav(wav_path, [0] * 2000 + [4000] * 2000 + [0] * 2000)
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.audio_detect_events(str(wav_path), min_silence_sec=0.1)

    assert result.success is True
    assert result.data is not None
    assert len(result.data["events"]) >= 2
    assert "summary" in result.data


def test_video_sample_frames_creates_frame_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"fake-video")
    video_path.with_name("clip.mp4.probe.json").write_text(
        json.dumps({"duration_sec": 2.0, "video_codec": "h264"}),
        encoding="utf-8",
    )
    import davinci_free_mcp.backend.media_analysis as media_analysis_module

    monkeypatch.setattr(media_analysis_module.shutil, "which", lambda _: None)
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.video_sample_frames(str(video_path), start=0.0, end=1.0, fps=2.0)

    assert result.success is True
    assert result.data is not None
    assert len(result.data["frames"]) == 3
    assert Path(result.data["frames"][0]["path"]).exists()
    assert result.data["frames_dir"].endswith("frames")


def test_video_extract_roi_frames_validates_positive_dimensions(tmp_path: Path) -> None:
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"fake-video")
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.video_extract_roi_frames(
        str(video_path),
        x=0,
        y=0,
        width=0,
        height=100,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_video_build_contact_sheet_creates_html_sheet(tmp_path: Path) -> None:
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"fake-video")
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    frame_paths = []
    for index in range(3):
        frame_path = frames_dir / f"frame_{index:04d}.jpg"
        frame_path.write_bytes(f"frame-{index}".encode("utf-8"))
        frame_paths.append(frame_path)
    (tmp_path / "frames.json").write_text(
        json.dumps(
            {
                "frames": [
                    {
                        "frame_index": index,
                        "timestamp_sec": float(index),
                        "path": str(frame_path),
                    }
                    for index, frame_path in enumerate(frame_paths)
                ]
            }
        ),
        encoding="utf-8",
    )
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.video_build_contact_sheet(str(video_path), frames_dir=str(frames_dir), columns=2, rows=2)

    assert result.success is True
    assert result.data is not None
    assert len(result.data["sheets"]) == 1
    assert Path(result.data["sheets"][0]["path"]).exists()


def test_video_detect_overlay_events_groups_changed_frames(tmp_path: Path) -> None:
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"fake-video")
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    payloads = [b"a", b"a", b"b", b"b", b"c"]
    frame_paths = []
    for index, payload in enumerate(payloads):
        frame_path = frames_dir / f"frame_{index:04d}.jpg"
        frame_path.write_bytes(payload)
        frame_paths.append(frame_path)
    (tmp_path / "frames.json").write_text(
        json.dumps(
            {
                "frames": [
                    {
                        "frame_index": index,
                        "timestamp_sec": index * 0.5,
                        "path": str(frame_path),
                    }
                    for index, frame_path in enumerate(frame_paths)
                ]
            }
        ),
        encoding="utf-8",
    )
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(runtime_dir=tmp_path / "runtime"),
    )

    result = service.video_detect_overlay_events(
        str(video_path),
        frames_dir=str(frames_dir),
        min_event_gap_sec=0.4,
    )

    assert result.success is True
    assert result.data is not None
    assert len(result.data["events"]) == 2
    assert result.data["events"][0]["reason"] == "frame_change"


def test_edit_plan_from_candidates_merges_close_events() -> None:
    service = ResolveBackendService(
        FakeBridge(BridgeResult.success("req-1", data={})),
        AppSettings(),
    )

    result = service.edit_plan_from_candidates(
        source_path="C:/videos/demo.mp4",
        target_timeline_name="Review",
        candidates=[
            {"time_sec": 10.0, "confidence": 0.8, "label": "First"},
            {"time_sec": 10.5, "confidence": 0.9, "label": "Second"},
            {"time_sec": 20.0, "confidence": 0.7, "label": "Third"},
        ],
    )

    assert result.success is True
    assert result.data is not None
    assert len(result.data["segments"]) == 2
    assert result.data["candidates"][1]["label"] == "Second"
    assert result.data["segments"][0]["label"] == "Second"
