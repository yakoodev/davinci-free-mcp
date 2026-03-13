"""Local media analysis helpers used by MCP tools."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import importlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import (
    AudioFeatureFlags,
    MediaAnalysisArtifact,
    MediaAnalysisManifest,
    MediaSegmentScreenshot,
    SegmentTimeRange,
    TranscriptSidecarData,
    TranscriptSidecarEngine,
    TranscriptSidecarSegment,
)

_PLACEHOLDER_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBUQEBAVFRUVFRUVFRUVFRUVFRUVFRUWFhUV"
    "FRUYHSggGBolGxUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OGhAQGi0fICUtLS0tLS0tLS0t"
    "LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAQMBIgACEQEDEQH/xAAX"
    "AAADAQAAAAAAAAAAAAAAAAAAAQID/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEAMQAAAB"
    "6gD/xAAZEAEBAQEBAQAAAAAAAAAAAAABEQIhMWH/2gAIAQEAAT8AfW1s2iP/xAAVEQEBAAAAAAAAAA"
    "AAAAAAAAABEP/aAAgBAgEBPwCf/8QAFBEBAAAAAAAAAAAAAAAAAAAAEP/aAAgBAwEBPwCf/9k="
)

_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mxf"}


class _TranscriptionSegment(BaseModel):
    start: float
    end: float
    text: str
    confidence: float | None = None
    source_track_indexes: list[int] = Field(default_factory=list)


class _ShotSegment(BaseModel):
    start: float
    end: float
    motion_score: float = 0.0
    black_frame_ratio: float = 0.0
    scene_change: bool = True


@dataclass(slots=True)
class _AnalysisContext:
    source: Path
    analysis_id: str
    artifacts_dir: Path
    params: dict[str, Any]


class LocalMediaAnalyzer:
    """File-system based audio/video analyzer with controlled fallbacks."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def _build_context(self, tool_name: str, path: str, params: dict[str, Any]) -> _AnalysisContext:
        source = Path(path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(f"Source file '{source}' was not found.")
        analysis_id = self._analysis_id(tool_name, source, params)
        artifacts_dir = self.settings.analysis_dir / analysis_id
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "screenshots").mkdir(parents=True, exist_ok=True)
        return _AnalysisContext(source=source, analysis_id=analysis_id, artifacts_dir=artifacts_dir, params=params)

    def _analysis_id(self, tool_name: str, source: Path, params: dict[str, Any]) -> str:
        digest = hashlib.sha256(
            json.dumps(
                {"tool_name": tool_name, "source": str(source), "params": params},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return digest[:16]

    def _build_manifest(
        self,
        tool_name: str,
        context: _AnalysisContext,
        artifacts: list[dict[str, Any]],
        warnings: list[str],
    ) -> dict[str, Any]:
        return MediaAnalysisManifest(
            tool_name=tool_name,
            source=str(context.source),
            analysis_id=context.analysis_id,
            artifacts_dir=str(context.artifacts_dir),
            created_at=datetime.now(UTC).isoformat(),
            input_params=context.params,
            artifacts=[MediaAnalysisArtifact.model_validate(item) for item in artifacts],
            warnings=warnings,
        ).model_dump(mode="json")

    def _artifact(self, kind: str, path: Path, label: str) -> dict[str, Any]:
        return MediaAnalysisArtifact(kind=kind, path=str(path.resolve()), label=label).model_dump(mode="json")

    def _write_json(self, path: Path, payload: dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=str(path.parent),
            prefix=f"{path.name}.",
            suffix=".tmp",
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
        return path

    def _write_text(self, path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _float_or_default(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _int_or_default(self, value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _parse_frame_rate(self, value: Any) -> float:
        if isinstance(value, str) and "/" in value:
            numerator, denominator = value.split("/", 1)
            denominator_value = self._float_or_default(denominator, 0.0)
            if denominator_value == 0:
                return 0.0
            return self._float_or_default(numerator, 0.0) / denominator_value
        return self._float_or_default(value, 0.0)

    def _load_sidecar_json(self, source: Path, suffix: str) -> dict[str, Any] | list[Any] | None:
        candidates = [
            source.with_name(f"{source.name}.{suffix}.json"),
            source.with_suffix(f"{source.suffix}.{suffix}.json"),
        ]
        for candidate in candidates:
            if not candidate.exists():
                continue
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                continue
        return None

    def _transcript_sidecar_path(self, source: Path) -> Path:
        return source.with_name(f"{source.name}.transcript.json")

    def _load_transcript_sidecar(self, source: Path) -> TranscriptSidecarData | None:
        sidecar_path = self._transcript_sidecar_path(source)
        if not sidecar_path.exists():
            return None
        try:
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
            return TranscriptSidecarData.model_validate(payload)
        except Exception:
            return None

    def list_audio_streams(self, source: Path) -> list[dict[str, Any]]:
        if source.suffix.lower() in _AUDIO_EXTENSIONS:
            metadata = self._probe_media(source)
            return [
                {
                    "stream_index": 0,
                    "codec_name": metadata.get("audio_codec") or metadata.get("codec"),
                    "language": None,
                    "title": None,
                    "start_time": 0.0,
                }
            ]
        ffprobe_path = shutil.which("ffprobe")
        if not ffprobe_path:
            metadata = self._probe_media(source)
            if self._has_audio_track(source, metadata):
                return [
                    {
                    "stream_index": 1,
                    "codec_name": metadata.get("audio_codec"),
                    "language": None,
                    "title": None,
                    "start_time": 0.0,
                }
            ]
            return []
        try:
            completed = subprocess.run(
                [
                    ffprobe_path,
                    "-v",
                    "error",
                    "-show_entries",
                    "stream=index,codec_type,codec_name:stream_tags=language,title",
                    "-of",
                    "json",
                    str(source),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout or "{}")
        except Exception:
            return []
        streams = []
        for stream in payload.get("streams") or []:
            if stream.get("codec_type") != "audio":
                continue
            tags = stream.get("tags") or {}
            streams.append(
                {
                    "stream_index": int(stream.get("index", 0)),
                    "codec_name": stream.get("codec_name"),
                    "language": tags.get("language"),
                    "title": tags.get("title"),
                    "start_time": self._float_or_default(stream.get("start_time"), 0.0),
                }
            )
        return streams

    def _extract_audio_for_transcription(
        self,
        source: Path,
        *,
        stream_index: int | None = None,
    ) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
        if source.suffix.lower() == ".wav":
            return source, None
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise RuntimeError("ffmpeg is required to extract audio for transcription.")
        temp_dir = tempfile.TemporaryDirectory(prefix="dfmcp-transcribe-")
        stream_suffix = "default" if stream_index is None else str(stream_index)
        temp_wav = Path(temp_dir.name) / f"transcription_{stream_suffix}.wav"
        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(source),
        ]
        if stream_index is not None:
            command.extend(["-map", f"0:{stream_index}"])
        command.extend(
            [
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                str(temp_wav),
            ]
        )
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        return temp_wav, temp_dir

    def _transcribe_with_faster_whisper(
        self,
        audio_path: Path,
        *,
        language: str | None,
    ) -> tuple[list[TranscriptSidecarSegment], str | None]:
        if self.settings.transcribe_provider != "faster_whisper":
            raise RuntimeError(
                f"Unsupported transcription provider '{self.settings.transcribe_provider}'."
            )
        try:
            faster_whisper = importlib.import_module("faster_whisper")
        except Exception as exc:
            raise RuntimeError("faster-whisper is not installed or failed to import.") from exc
        whisper_model = faster_whisper.WhisperModel(
            self.settings.transcribe_model,
            device=self.settings.transcribe_device,
            compute_type=self.settings.transcribe_compute_type,
        )
        segments_iter, info = whisper_model.transcribe(
            str(audio_path),
            language=language,
            beam_size=self.settings.transcribe_beam_size,
        )
        segments = []
        for segment in segments_iter:
            text = str(getattr(segment, "text", "") or "").strip()
            if not text:
                continue
            confidence = getattr(segment, "avg_logprob", None)
            segments.append(
                TranscriptSidecarSegment(
                    start=float(getattr(segment, "start", 0.0)),
                    end=float(getattr(segment, "end", 0.0)),
                    text=text,
                    confidence=float(confidence) if confidence is not None else None,
                )
            )
        detected_language = getattr(info, "language", None)
        return segments, detected_language

    def _normalize_sidecar_segments(
        self,
        segments: list[TranscriptSidecarSegment | dict[str, Any] | Any],
        *,
        track_index: int | None = None,
        start_time_offset: float = 0.0,
    ) -> list[TranscriptSidecarSegment]:
        normalized = []
        for segment in segments:
            if isinstance(segment, TranscriptSidecarSegment):
                model = segment
            elif isinstance(segment, dict):
                model = TranscriptSidecarSegment.model_validate(segment)
            else:
                text = str(getattr(segment, "text", "") or "").strip()
                if not text:
                    continue
                confidence = getattr(segment, "confidence", getattr(segment, "avg_logprob", None))
                model = TranscriptSidecarSegment(
                    start=float(getattr(segment, "start", 0.0)),
                    end=float(getattr(segment, "end", 0.0)),
                    text=text,
                    confidence=float(confidence) if confidence is not None else None,
                    track_index=track_index,
                )
            if track_index is not None and model.track_index is None:
                model = model.model_copy(update={"track_index": track_index})
            if start_time_offset:
                model = model.model_copy(
                    update={
                        "start": max(0.0, model.start + start_time_offset),
                        "end": max(0.0, model.end + start_time_offset),
                    }
                )
            normalized.append(model)
        return normalized

    def resolve_transcript_sidecar(
        self,
        source: Path,
        *,
        language: str | None,
        force_rebuild: bool = False,
    ) -> TranscriptSidecarData:
        if not force_rebuild:
            existing = self._load_transcript_sidecar(source)
            if existing is not None:
                return existing
        audio_streams = self.list_audio_streams(source)
        if not audio_streams and source.suffix.lower() in _AUDIO_EXTENSIONS:
            audio_streams = [{"stream_index": 0, "codec_name": None, "language": None, "title": None, "start_time": 0.0}]
        merged_segments: list[TranscriptSidecarSegment] = []
        detected_language: str | None = None
        for stream in audio_streams:
            stream_index = int(stream["stream_index"])
            audio_path, temp_dir = self._extract_audio_for_transcription(
                source,
                stream_index=None if source.suffix.lower() in _AUDIO_EXTENSIONS else stream_index,
            )
            try:
                segments, stream_language = self._transcribe_with_faster_whisper(
                    audio_path,
                    language=language,
                )
            finally:
                if temp_dir is not None:
                    temp_dir.cleanup()
            normalized_segments = self._normalize_sidecar_segments(
                segments,
                track_index=stream_index,
                start_time_offset=self._float_or_default(stream.get("start_time"), 0.0),
            )
            if detected_language is None and stream_language is not None:
                detected_language = stream_language
            merged_segments.extend(normalized_segments)
        merged_segments.sort(key=lambda item: (item.start, item.track_index or -1, item.end))
        metadata = self._probe_media(source)
        sidecar = TranscriptSidecarData(
            source=str(source),
            created_at=datetime.now(UTC).isoformat(),
            engine=TranscriptSidecarEngine(
                name="faster-whisper",
                model=self.settings.transcribe_model,
                device=self.settings.transcribe_device,
                compute_type=self.settings.transcribe_compute_type,
            ),
            language=language,
            duration_sec=self._duration_from_metadata(metadata),
            transcript_status="ok" if merged_segments else "no_speech_detected",
            segments=[segment.model_dump(mode="json") for segment in merged_segments],
        )
        self._write_json_atomic(
            self._transcript_sidecar_path(source),
            sidecar.model_dump(mode="json"),
        )
        return sidecar

    def _normalize_ffprobe_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        fmt = payload.get("format") or {}
        if "duration" in fmt:
            result["duration_sec"] = self._float_or_default(fmt.get("duration"), 0.0)
        if "bit_rate" in fmt:
            result["bit_rate"] = self._int_or_default(fmt.get("bit_rate"), 0)
        for stream in payload.get("streams") or []:
            codec_type = stream.get("codec_type")
            if codec_type == "audio":
                result["audio_codec"] = stream.get("codec_name")
                result["sample_rate"] = self._int_or_default(stream.get("sample_rate"), 0)
                result["channels"] = self._int_or_default(stream.get("channels"), 0)
            elif codec_type == "video":
                result["video_codec"] = stream.get("codec_name")
                result["width"] = self._int_or_default(stream.get("width"), 0)
                result["height"] = self._int_or_default(stream.get("height"), 0)
                result["fps"] = self._parse_frame_rate(stream.get("r_frame_rate"))
        return result

    def _fallback_probe(self, source: Path) -> dict[str, Any]:
        suffix = source.suffix.lower()
        if suffix == ".wav":
            with contextlib.closing(wave.open(str(source), "rb")) as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                duration_sec = frames / float(sample_rate) if sample_rate else 0.0
                return {
                    "duration_sec": duration_sec,
                    "sample_rate": sample_rate,
                    "channels": wav_file.getnchannels(),
                    "codec": "pcm",
                    "bit_rate": sample_rate * wav_file.getsampwidth() * 8 * wav_file.getnchannels(),
                    "audio_codec": "pcm",
                }
        return {
            "duration_sec": 0.0,
            "bit_rate": 0,
            "video_codec": "unknown" if suffix in _VIDEO_EXTENSIONS else None,
            "audio_codec": "unknown" if suffix in _AUDIO_EXTENSIONS or suffix in _VIDEO_EXTENSIONS else None,
            "fps": 0.0,
            "width": 0,
            "height": 0,
            "sample_rate": 0,
            "channels": 0,
        }

    def _probe_media(self, source: Path) -> dict[str, Any]:
        sidecar = self._load_sidecar_json(source, "probe")
        if isinstance(sidecar, dict):
            return sidecar
        ffprobe_path = shutil.which("ffprobe")
        if ffprobe_path:
            try:
                completed = subprocess.run(
                    [
                        ffprobe_path,
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration,bit_rate:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
                        "-of",
                        "json",
                        str(source),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return self._normalize_ffprobe_payload(json.loads(completed.stdout or "{}"))
            except Exception:
                pass
        return self._fallback_probe(source)

    def _duration_from_metadata(self, metadata: dict[str, Any]) -> float:
        return self._float_or_default(metadata.get("duration_sec") or metadata.get("duration"), 0.0)

    def _has_audio_track(self, source: Path, metadata: dict[str, Any]) -> bool:
        if metadata.get("audio_codec") or metadata.get("sample_rate"):
            return True
        return source.suffix.lower() in _AUDIO_EXTENSIONS or source.suffix.lower() in _VIDEO_EXTENSIONS

    def _has_video_track(self, source: Path, metadata: dict[str, Any]) -> bool:
        if metadata.get("video_codec") or metadata.get("width") or metadata.get("height"):
            return True
        return source.suffix.lower() in _VIDEO_EXTENSIONS

    def _rms_pcm(self, frames: bytes, sample_width: int) -> float:
        if sample_width <= 0:
            return 0.0
        if sample_width == 1:
            samples = [abs(sample - 128) for sample in frames]
        else:
            sample_count = len(frames) // sample_width
            samples = [
                abs(int.from_bytes(frames[index * sample_width:(index + 1) * sample_width], "little", signed=True))
                for index in range(sample_count)
            ]
        if not samples:
            return 0.0
        square_mean = sum(sample * sample for sample in samples) / len(samples)
        return math.sqrt(square_mean)

    def _measure_wav_silence(self, source: Path) -> tuple[float, float]:
        with contextlib.closing(wave.open(str(source), "rb")) as wav_file:
            frame_rate = wav_file.getframerate()
            chunk_size = max(1, int(frame_rate * 0.25))
            total_chunks = 0
            silent_chunks = 0
            energy_total = 0.0
            while True:
                frames = wav_file.readframes(chunk_size)
                if not frames:
                    break
                total_chunks += 1
                rms = self._rms_pcm(frames, wav_file.getsampwidth())
                energy_total += rms
                if rms < 200:
                    silent_chunks += 1
            if total_chunks == 0:
                return 1.0, 0.0
            return silent_chunks / total_chunks, energy_total / total_chunks

    def audio_probe(self, path: str) -> dict[str, Any]:
        context = self._build_context("audio_probe", path, {})
        warnings: list[str] = []
        metadata = self._probe_media(context.source)
        if context.source.suffix.lower() == ".wav":
            silence_ratio, avg_energy = self._measure_wav_silence(context.source)
            speech_likelihood = max(0.0, min(1.0, avg_energy / 3000.0))
        else:
            silence_ratio = 0.0
            speech_likelihood = 0.0
            warnings.append("Detailed audio probing is limited for non-WAV sources without ffprobe metadata.")
        manifest_path = self._write_json(
            context.artifacts_dir / "manifest.json",
            self._build_manifest("audio_probe", context, [], warnings),
        )
        data = {
            "source": str(context.source),
            "analysis_id": context.analysis_id,
            "artifacts_dir": str(context.artifacts_dir),
            "media": {
                "duration_sec": self._duration_from_metadata(metadata),
                "sample_rate": self._int_or_default(metadata.get("sample_rate"), 0),
                "channels": self._int_or_default(metadata.get("channels"), 0),
                "codec": str(metadata.get("codec") or metadata.get("audio_codec") or "unknown"),
                "bit_rate": self._int_or_default(metadata.get("bit_rate"), 0),
            },
            "audio": {
                "has_audio": self._has_audio_track(context.source, metadata),
                "speech_likelihood": speech_likelihood,
                "silence_ratio": silence_ratio,
            },
            "artifacts": [self._artifact("json", manifest_path, "manifest")],
        }
        return {"data": data, "warnings": warnings}

    def _load_transcript_segments(self, source: Path) -> list[_TranscriptionSegment]:
        sidecar = self._load_transcript_sidecar(source)
        if sidecar is None:
            return []
        return [
            _TranscriptionSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text,
                confidence=segment.confidence,
                source_track_indexes=[segment.track_index] if segment.track_index is not None else [],
            )
            for segment in sidecar.segments
        ]

    def _merge_transcript_segments(
        self,
        raw_segments: list[_TranscriptionSegment],
        max_segment_sec: float,
    ) -> list[_TranscriptionSegment]:
        if not raw_segments:
            return []
        merged: list[_TranscriptionSegment] = []
        current = raw_segments[0].model_copy(deep=True)
        for segment in raw_segments[1:]:
            if (
                segment.end - current.start <= max_segment_sec
                and segment.source_track_indexes == current.source_track_indexes
            ):
                confidence_values = [value for value in (current.confidence, segment.confidence) if value is not None]
                current.end = segment.end
                current.text = f"{current.text} {segment.text}".strip()
                current.confidence = sum(confidence_values) / len(confidence_values) if confidence_values else None
            else:
                merged.append(current)
                current = segment.model_copy(deep=True)
        merged.append(current)
        return merged

    def audio_transcribe_segments(
        self,
        path: str,
        *,
        language: str | None,
        max_segment_sec: float,
    ) -> dict[str, Any]:
        context = self._build_context(
            "audio_transcribe_segments",
            path,
            {"language": language, "max_segment_sec": max_segment_sec},
        )
        warnings: list[str] = []
        sidecar = self.resolve_transcript_sidecar(context.source, language=language)
        segments = self._merge_transcript_segments(self._load_transcript_segments(context.source), max_segment_sec)
        transcript_status = sidecar.transcript_status
        if not segments:
            warnings.append("No speech was detected in the source audio.")
        payload_segments = [
            {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "track_index": segment.source_track_indexes[0] if segment.source_track_indexes else None,
            }
            for segment in segments
        ]
        transcript_json_path = self._transcript_sidecar_path(context.source)
        transcript_copy_path = self._write_json(
            context.artifacts_dir / "transcript.json",
            sidecar.model_dump(mode="json"),
        )
        transcript_text_path = self._write_text(
            context.artifacts_dir / "transcript.txt",
            "\n".join(segment["text"] for segment in payload_segments),
        )
        artifacts = [
            self._artifact("json", transcript_json_path, "transcript_json"),
            self._artifact("json", transcript_copy_path, "transcript_copy"),
            self._artifact("text", transcript_text_path, "transcript_text"),
        ]
        manifest_path = self._write_json(
            context.artifacts_dir / "manifest.json",
            self._build_manifest("audio_transcribe_segments", context, artifacts, warnings),
        )
        artifacts.append(self._artifact("json", manifest_path, "manifest"))
        data = {
            "source": str(context.source),
            "analysis_id": context.analysis_id,
            "artifacts_dir": str(context.artifacts_dir),
            "transcript_status": transcript_status,
            "segments": payload_segments,
            "artifacts": artifacts,
        }
        return {"data": data, "warnings": warnings}

    def _classify_audio_energy(self, rms: float) -> str:
        if rms < 200:
            return "silence"
        if rms < 900:
            return "low_energy"
        if rms < 2000:
            return "noise"
        if rms < 5000:
            return "music_like"
        return "high_energy"

    def _finalize_audio_event(
        self,
        start: float,
        end: float,
        energy_values: list[float],
        event_type: str,
    ) -> dict[str, Any]:
        label_map = {
            "silence": "Silence",
            "music_like": "Music-like segment",
            "noise": "Noise floor",
            "impact": "Impact sound",
            "high_energy": "High-energy segment",
            "low_energy": "Low-energy segment",
        }
        energy = sum(energy_values) / max(1, len(energy_values))
        return {
            "start": start,
            "end": end,
            "event_type": event_type,
            "energy": energy,
            "label": label_map.get(event_type, event_type.replace("_", " ").title()),
        }

    def _detect_audio_events(
        self,
        source: Path,
        min_silence_sec: float,
        warnings: list[str],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        sidecar = self._load_sidecar_json(source, "events")
        if isinstance(sidecar, dict):
            return sidecar.get("summary", {}), sidecar.get("events", [])
        if source.suffix.lower() != ".wav":
            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                with tempfile.TemporaryDirectory(prefix="dfmcp-audio-") as temp_dir:
                    temp_wav = Path(temp_dir) / "extracted.wav"
                    try:
                        subprocess.run(
                            [
                                ffmpeg_path,
                                "-y",
                                "-i",
                                str(source),
                                "-vn",
                                "-ac",
                                "1",
                                "-ar",
                                "16000",
                                str(temp_wav),
                            ],
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                        return self._detect_audio_events(temp_wav, min_silence_sec, warnings)
                    except Exception:
                        warnings.append("ffmpeg audio extraction failed; falling back to a single low-energy event.")
            else:
                warnings.append("ffmpeg is unavailable for audio extraction; falling back to a single low-energy event.")
            duration_sec = self._duration_from_metadata(self._probe_media(source))
            return {
                "speech_detected": False,
                "music_detected": False,
                "silence_ranges_count": 0,
            }, [{
                "start": 0.0,
                "end": duration_sec,
                "event_type": "low_energy",
                "energy": 0.0,
                "label": "Fallback event",
            }]
        with contextlib.closing(wave.open(str(source), "rb")) as wav_file:
            frame_rate = wav_file.getframerate()
            chunk_duration = 0.25
            chunk_size = max(1, int(frame_rate * chunk_duration))
            total_frames = wav_file.getnframes()
            duration_sec = total_frames / float(frame_rate) if frame_rate else 0.0
            chunks: list[tuple[float, float, float]] = []
            start = 0.0
            while True:
                frames = wav_file.readframes(chunk_size)
                if not frames:
                    break
                end = min(duration_sec, start + chunk_duration)
                chunks.append((start, end, self._rms_pcm(frames, wav_file.getsampwidth())))
                start = end
        if not chunks:
            return {"speech_detected": False, "music_detected": False, "silence_ranges_count": 1}, [{
                "start": 0.0,
                "end": 0.0,
                "event_type": "silence",
                "energy": 0.0,
                "label": "Empty audio",
            }]
        events: list[dict[str, Any]] = []
        silence_ranges_count = 0
        buffer_start, buffer_end, first_rms = chunks[0]
        buffer_type = self._classify_audio_energy(first_rms)
        buffer_values = [first_rms]
        for chunk_start, chunk_end, rms in chunks[1:]:
            chunk_type = self._classify_audio_energy(rms)
            if chunk_type == buffer_type:
                buffer_end = chunk_end
                buffer_values.append(rms)
                continue
            event = self._finalize_audio_event(buffer_start, buffer_end, buffer_values, buffer_type)
            if event["event_type"] != "silence" or (event["end"] - event["start"]) >= min_silence_sec:
                events.append(event)
                if event["event_type"] == "silence":
                    silence_ranges_count += 1
            buffer_start, buffer_end, buffer_type, buffer_values = chunk_start, chunk_end, chunk_type, [rms]
        event = self._finalize_audio_event(buffer_start, buffer_end, buffer_values, buffer_type)
        if event["event_type"] != "silence" or (event["end"] - event["start"]) >= min_silence_sec:
            events.append(event)
            if event["event_type"] == "silence":
                silence_ranges_count += 1
        return {
            "speech_detected": any(item["event_type"] in {"noise", "high_energy"} for item in events),
            "music_detected": any(item["event_type"] == "music_like" for item in events),
            "silence_ranges_count": silence_ranges_count,
        }, events

    def audio_detect_events(self, path: str, *, min_silence_sec: float) -> dict[str, Any]:
        context = self._build_context(
            "audio_detect_events",
            path,
            {"min_silence_sec": min_silence_sec},
        )
        warnings: list[str] = []
        summary, events = self._detect_audio_events(context.source, min_silence_sec, warnings)
        events_path = self._write_json(
            context.artifacts_dir / "events.json",
            {"summary": summary, "events": events},
        )
        artifacts = [self._artifact("json", events_path, "events")]
        manifest_path = self._write_json(
            context.artifacts_dir / "manifest.json",
            self._build_manifest("audio_detect_events", context, artifacts, warnings),
        )
        artifacts.append(self._artifact("json", manifest_path, "manifest"))
        data = {
            "source": str(context.source),
            "analysis_id": context.analysis_id,
            "artifacts_dir": str(context.artifacts_dir),
            "events": events,
            "summary": summary,
            "artifacts": artifacts,
        }
        return {"data": data, "warnings": warnings}

    def video_probe(self, path: str) -> dict[str, Any]:
        context = self._build_context("video_probe", path, {})
        warnings: list[str] = []
        metadata = self._probe_media(context.source)
        manifest_path = self._write_json(
            context.artifacts_dir / "manifest.json",
            self._build_manifest("video_probe", context, [], warnings),
        )
        data = {
            "source": str(context.source),
            "analysis_id": context.analysis_id,
            "artifacts_dir": str(context.artifacts_dir),
            "media": {
                "duration_sec": self._duration_from_metadata(metadata),
                "fps": self._float_or_default(metadata.get("fps"), 0.0),
                "width": self._int_or_default(metadata.get("width"), 0),
                "height": self._int_or_default(metadata.get("height"), 0),
                "video_codec": str(metadata.get("video_codec") or "unknown"),
                "audio_codec": str(metadata.get("audio_codec")) if metadata.get("audio_codec") else None,
            },
            "tracks": {
                "has_video": self._has_video_track(context.source, metadata),
                "has_audio": self._has_audio_track(context.source, metadata),
            },
            "artifacts": [self._artifact("json", manifest_path, "manifest")],
        }
        return {"data": data, "warnings": warnings}

    def _load_or_build_shots(self, source: Path, min_shot_sec: float, warnings: list[str]) -> list[_ShotSegment]:
        sidecar = self._load_sidecar_json(source, "shots")
        if isinstance(sidecar, dict):
            raw_shots = sidecar.get("shots", [])
        elif isinstance(sidecar, list):
            raw_shots = sidecar
        else:
            raw_shots = []
        if raw_shots:
            return [_ShotSegment.model_validate(item) for item in raw_shots]
        warnings.append("Shot detection sidecar was not found; using a single fallback scene segment.")
        duration_sec = self._duration_from_metadata(self._probe_media(source))
        if duration_sec <= 0:
            duration_sec = min_shot_sec
        return [_ShotSegment(start=0.0, end=max(duration_sec, min_shot_sec), scene_change=False)]

    def video_detect_shots(
        self,
        path: str,
        *,
        cut_threshold: float,
        min_shot_sec: float,
    ) -> dict[str, Any]:
        context = self._build_context(
            "video_detect_shots",
            path,
            {"cut_threshold": cut_threshold, "min_shot_sec": min_shot_sec},
        )
        warnings: list[str] = []
        shots = self._load_or_build_shots(context.source, min_shot_sec, warnings)
        shot_payload = [
            {
                "shot_index": index,
                "start": shot.start,
                "end": shot.end,
                "segment_source": "scene",
                "visual_features": {
                    "scene_change": shot.scene_change,
                    "motion_score": shot.motion_score,
                    "black_frame_ratio": shot.black_frame_ratio,
                },
            }
            for index, shot in enumerate(shots)
        ]
        segments_path = self._write_json(context.artifacts_dir / "segments.json", {"shots": shot_payload})
        artifacts = [self._artifact("json", segments_path, "shots")]
        manifest_path = self._write_json(
            context.artifacts_dir / "manifest.json",
            self._build_manifest("video_detect_shots", context, artifacts, warnings),
        )
        artifacts.append(self._artifact("json", manifest_path, "manifest"))
        data = {
            "source": str(context.source),
            "analysis_id": context.analysis_id,
            "artifacts_dir": str(context.artifacts_dir),
            "shots": shot_payload,
            "artifacts": artifacts,
        }
        return {"data": data, "warnings": warnings}

    def _build_screenshot_timestamps(self, start: float, end: float, count: int) -> list[float]:
        if count <= 1 or end <= start:
            return [start + max(0.0, end - start) / 2.0]
        step = (end - start) / float(count + 1)
        return [start + step * (index + 1) for index in range(count)]

    def _extract_screenshots(
        self,
        source: Path,
        artifacts_dir: Path,
        start: float,
        end: float,
        screenshots_per_segment: int,
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        duration = max(0.0, end - start)
        target_count = screenshots_per_segment
        if screenshots_per_segment == 1:
            if duration > 30:
                target_count = 3
            elif duration > 12:
                target_count = 2
        ffmpeg_path = shutil.which("ffmpeg")
        screenshots = []
        for index, timestamp in enumerate(self._build_screenshot_timestamps(start, end, target_count)):
            screenshot_path = artifacts_dir / "screenshots" / f"{start:.3f}_{end:.3f}_{index}.jpg"
            if ffmpeg_path:
                try:
                    subprocess.run(
                        [
                            ffmpeg_path,
                            "-y",
                            "-ss",
                            f"{timestamp:.3f}",
                            "-i",
                            str(source),
                            "-frames:v",
                            "1",
                            str(screenshot_path),
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                except Exception:
                    screenshot_path.write_bytes(_PLACEHOLDER_JPEG)
                    warnings.append("ffmpeg screenshot extraction failed; placeholder screenshots were written.")
            else:
                screenshot_path.write_bytes(_PLACEHOLDER_JPEG)
                placeholder_warning = "ffmpeg screenshot extraction is unavailable; placeholder screenshots were written."
                if placeholder_warning not in warnings:
                    warnings.append(placeholder_warning)
            screenshots.append(
                MediaSegmentScreenshot(
                    path=str(screenshot_path.resolve()),
                    timestamp_sec=timestamp,
                    kind="midpoint" if index == target_count // 2 else "boundary",
                ).model_dump(mode="json")
            )
        return screenshots

    def video_extract_segment_screenshots(
        self,
        path: str,
        *,
        segments: list[dict[str, Any]],
        screenshots_per_segment: int,
    ) -> dict[str, Any]:
        context = self._build_context(
            "video_extract_segment_screenshots",
            path,
            {"segments": segments, "screenshots_per_segment": screenshots_per_segment},
        )
        warnings: list[str] = []
        payload_segments = []
        artifacts: list[dict[str, Any]] = []
        for segment in [SegmentTimeRange.model_validate(item) for item in segments]:
            screenshots = self._extract_screenshots(
                context.source,
                context.artifacts_dir,
                segment.start,
                segment.end,
                screenshots_per_segment,
                warnings,
            )
            payload_segments.append({"start": segment.start, "end": segment.end, "screenshots": screenshots})
            artifacts.extend(
                self._artifact("image", Path(screenshot["path"]), f"screenshot_{index}")
                for index, screenshot in enumerate(screenshots)
            )
        segments_path = self._write_json(context.artifacts_dir / "segments.json", {"segments": payload_segments})
        artifacts.append(self._artifact("json", segments_path, "segments"))
        manifest_path = self._write_json(
            context.artifacts_dir / "manifest.json",
            self._build_manifest("video_extract_segment_screenshots", context, artifacts, warnings),
        )
        artifacts.append(self._artifact("json", manifest_path, "manifest"))
        data = {
            "source": str(context.source),
            "analysis_id": context.analysis_id,
            "artifacts_dir": str(context.artifacts_dir),
            "segments": payload_segments,
            "artifacts": artifacts,
        }
        return {"data": data, "warnings": warnings}

    def _audio_feature_defaults(self, source: Path, metadata: dict[str, Any]) -> dict[str, Any]:
        has_audio = self._has_audio_track(source, metadata)
        return AudioFeatureFlags(
            speech_detected=False,
            music_detected=has_audio,
            silence=not has_audio,
            energy=0.0,
        ).model_dump(mode="json")

    def _snap_to_shots(self, start: float, end: float, shots: list[_ShotSegment]) -> tuple[float, float]:
        snapped_start = start
        snapped_end = end
        for shot in shots:
            if shot.start <= start <= shot.end:
                snapped_start = shot.start
            if shot.start <= end <= shot.end:
                snapped_end = shot.end
        return snapped_start, snapped_end

    def _match_shot_feature(self, start: float, end: float, shots: list[_ShotSegment], feature_name: str) -> float:
        for shot in shots:
            if shot.start <= start <= shot.end or shot.start <= end <= shot.end:
                return float(getattr(shot, feature_name))
        return 0.0

    def _finalize_segmented_video_result(
        self,
        *,
        tool_name: str,
        context: _AnalysisContext,
        warnings: list[str],
        segmentation_mode: str,
        segments: list[dict[str, Any]],
        screenshots_per_segment: int,
        transcript_status: str | None = None,
    ) -> dict[str, Any]:
        artifacts: list[dict[str, Any]] = []
        payload_segments = []
        for index, segment in enumerate(segments):
            screenshots = self._extract_screenshots(
                context.source,
                context.artifacts_dir,
                float(segment["start"]),
                float(segment["end"]),
                screenshots_per_segment,
                warnings,
            )
            screenshot_path = screenshots[0]["path"] if screenshots else None
            if tool_name == "video_segment_from_speech":
                payload = {
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment.get("transcript"),
                    "track_index": segment.get("source_track_indexes", [None])[0],
                    "screenshot_path": screenshot_path,
                }
            else:
                payload = {
                    "segment_index": index,
                    "start": segment["start"],
                    "end": segment["end"],
                    "segment_source": segment["segment_source"],
                    "transcript": segment.get("transcript"),
                    "audio_event": segment.get("audio_event"),
                    "audio_features": segment["audio_features"],
                    "visual_features": segment.get("visual_features"),
                    "source_track_indexes": segment.get("source_track_indexes", []),
                    "screenshots": screenshots,
                }
            payload_segments.append(payload)
            artifacts.extend(
                self._artifact("image", Path(screenshot["path"]), f"screenshot_{index}_{shot_index}")
                for shot_index, screenshot in enumerate(screenshots)
            )
        segments_path = self._write_json(context.artifacts_dir / "segments.json", {"segments": payload_segments})
        artifacts.append(self._artifact("json", segments_path, "segments"))
        if transcript_status is not None:
            transcript_path = self._transcript_sidecar_path(context.source)
            artifacts.append(self._artifact("json", transcript_path, "transcript"))
            transcript_sidecar = self._load_transcript_sidecar(context.source)
            if transcript_sidecar is not None:
                transcript_copy_path = self._write_json(
                    context.artifacts_dir / "transcript.json",
                    transcript_sidecar.model_dump(mode="json"),
                )
                artifacts.append(self._artifact("json", transcript_copy_path, "transcript_copy"))
        manifest_path = self._write_json(
            context.artifacts_dir / "manifest.json",
            self._build_manifest(tool_name, context, artifacts, warnings),
        )
        artifacts.append(self._artifact("json", manifest_path, "manifest"))
        data = {
            "source": str(context.source),
            "analysis_id": context.analysis_id,
            "artifacts_dir": str(context.artifacts_dir),
            "segmentation_mode": segmentation_mode,
            "segments": payload_segments,
            "artifacts": artifacts,
        }
        if transcript_status is not None:
            data["transcript_status"] = transcript_status
        return {"data": data, "warnings": warnings}

    def video_segment_from_speech(
        self,
        path: str,
        *,
        language: str | None,
        max_segment_sec: float,
        screenshots_per_segment: int,
    ) -> dict[str, Any]:
        context = self._build_context(
            "video_segment_from_speech",
            path,
            {
                "language": language,
                "max_segment_sec": max_segment_sec,
                "screenshots_per_segment": screenshots_per_segment,
            },
        )
        warnings: list[str] = []
        metadata = self._probe_media(context.source)
        if not self._has_audio_track(context.source, metadata):
            warnings.append("Video has no audio track; use video_segment_visual for silent material.")
            return self._finalize_segmented_video_result(
                tool_name="video_segment_from_speech",
                context=context,
                warnings=warnings,
                segmentation_mode="speech",
                segments=[],
                screenshots_per_segment=screenshots_per_segment,
                transcript_status="no_speech_detected",
            )
        sidecar = self.resolve_transcript_sidecar(context.source, language=language)
        merged = self._merge_transcript_segments(self._load_transcript_segments(context.source), max_segment_sec)
        if not merged:
            warnings.append("No speech was detected; use video_segment_visual or video_segment_audio_visual.")
        segments = [
            {
                "start": item.start,
                "end": item.end,
                "segment_source": "speech",
                "transcript": item.text,
                "audio_event": None,
                "audio_features": {
                    "speech_detected": True,
                    "music_detected": False,
                    "silence": False,
                    "energy": item.confidence if item.confidence is not None else 0.5,
                },
                "visual_features": None,
                "source_track_indexes": item.source_track_indexes,
            }
            for item in merged
        ]
        return self._finalize_segmented_video_result(
            tool_name="video_segment_from_speech",
            context=context,
            warnings=warnings,
            segmentation_mode="speech",
            segments=segments,
            screenshots_per_segment=screenshots_per_segment,
            transcript_status=sidecar.transcript_status,
        )

    def video_segment_visual(
        self,
        path: str,
        *,
        segment_mode: str,
        window_sec: float,
        screenshots_per_segment: int,
    ) -> dict[str, Any]:
        context = self._build_context(
            "video_segment_visual",
            path,
            {
                "segment_mode": segment_mode,
                "window_sec": window_sec,
                "screenshots_per_segment": screenshots_per_segment,
            },
        )
        warnings: list[str] = []
        metadata = self._probe_media(context.source)
        duration_sec = max(self._duration_from_metadata(metadata), window_sec)
        if segment_mode == "shots":
            shots = self._load_or_build_shots(context.source, 1.0, warnings)
            if len(shots) <= 1:
                warnings.append("Reliable scene cuts were not found; consider video_segment_visual with segment_mode='fixed_window'.")
            segments = [
                {
                    "start": shot.start,
                    "end": shot.end,
                    "segment_source": "scene",
                    "audio_event": None,
                    "audio_features": self._audio_feature_defaults(context.source, metadata),
                    "visual_features": {
                        "scene_change": shot.scene_change,
                        "motion_score": shot.motion_score,
                        "black_frame_ratio": shot.black_frame_ratio,
                    },
                }
                for shot in shots
            ]
        elif segment_mode == "fixed_window":
            segments = []
            cursor = 0.0
            index = 0
            while cursor < duration_sec:
                end = min(duration_sec, cursor + window_sec)
                segments.append(
                    {
                        "start": cursor,
                        "end": end,
                        "segment_source": "fixed_window",
                        "audio_event": None,
                        "audio_features": self._audio_feature_defaults(context.source, metadata),
                        "visual_features": {
                            "scene_change": index > 0,
                            "motion_score": 0.0,
                            "black_frame_ratio": 0.0,
                        },
                    }
                )
                cursor = end
                index += 1
        else:
            raise ValueError("segment_mode must be 'shots' or 'fixed_window'.")
        return self._finalize_segmented_video_result(
            tool_name="video_segment_visual",
            context=context,
            warnings=warnings,
            segmentation_mode="visual",
            segments=segments,
            screenshots_per_segment=screenshots_per_segment,
        )

    def video_segment_audio_visual(
        self,
        path: str,
        *,
        min_silence_sec: float,
        screenshots_per_segment: int,
    ) -> dict[str, Any]:
        context = self._build_context(
            "video_segment_audio_visual",
            path,
            {
                "min_silence_sec": min_silence_sec,
                "screenshots_per_segment": screenshots_per_segment,
            },
        )
        warnings: list[str] = []
        shots = self._load_or_build_shots(context.source, 1.0, warnings)
        use_shot_snapping = len(shots) > 1 or any(shot.scene_change for shot in shots)
        _, audio_events = self._detect_audio_events(context.source, min_silence_sec, warnings)
        segments = []
        for event in audio_events:
            snapped_start = float(event["start"])
            snapped_end = float(event["end"])
            if use_shot_snapping:
                snapped_start, snapped_end = self._snap_to_shots(snapped_start, snapped_end, shots)
            segments.append(
                {
                    "start": snapped_start,
                    "end": snapped_end,
                    "segment_source": "audio_event",
                    "audio_event": event["event_type"],
                    "audio_features": {
                        "speech_detected": False,
                        "music_detected": event["event_type"] == "music_like",
                        "silence": event["event_type"] == "silence",
                        "energy": event["energy"],
                    },
                    "visual_features": {
                        "scene_change": use_shot_snapping,
                        "motion_score": self._match_shot_feature(snapped_start, snapped_end, shots, "motion_score") if use_shot_snapping else 0.0,
                        "black_frame_ratio": self._match_shot_feature(snapped_start, snapped_end, shots, "black_frame_ratio") if use_shot_snapping else 0.0,
                    },
                }
            )
        return self._finalize_segmented_video_result(
            tool_name="video_segment_audio_visual",
            context=context,
            warnings=warnings,
            segmentation_mode="audio_visual",
            segments=segments,
            screenshots_per_segment=screenshots_per_segment,
        )
