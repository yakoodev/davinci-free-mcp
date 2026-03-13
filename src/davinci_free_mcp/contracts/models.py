"""Core data contracts for the first vertical slice."""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

BridgeErrorCategory = Literal[
    "bridge_unavailable",
    "resolve_not_ready",
    "no_project_open",
    "no_current_timeline",
    "object_not_found",
    "unsupported_command",
    "unsupported_in_free_mode",
    "validation_error",
    "execution_failure",
    "timeout",
]


class BridgeError(BaseModel):
    """Normalized bridge or executor error."""

    category: BridgeErrorCategory
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class BridgeCommand(BaseModel):
    """Transport-agnostic command envelope."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    command: str
    target: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = Field(default=5000, gt=0)
    context: dict[str, Any] = Field(default_factory=dict)


class BridgeResult(BaseModel):
    """Transport-agnostic result envelope."""

    request_id: str
    ok: bool
    data: dict[str, Any] | None = None
    error: BridgeError | None = None
    warnings: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def success(
        cls,
        request_id: str,
        data: dict[str, Any] | None = None,
        *,
        warnings: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> "BridgeResult":
        return cls(
            request_id=request_id,
            ok=True,
            data=data or {},
            warnings=warnings or [],
            meta=meta or {},
        )

    @classmethod
    def failure(
        cls,
        request_id: str,
        category: BridgeErrorCategory,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> "BridgeResult":
        return cls(
            request_id=request_id,
            ok=False,
            error=BridgeError(
                category=category,
                message=message,
                details=details or {},
            ),
            warnings=warnings or [],
            meta=meta or {},
        )


class ResolveBridgeStatus(BaseModel):
    available: bool
    adapter: str


class ResolveExecutorStatus(BaseModel):
    running: bool


class ResolveAppStatus(BaseModel):
    connected: bool
    product_name: str | None = None
    version: str | None = None


class ResolveProjectStatus(BaseModel):
    open: bool
    name: str | None = None


class ResolveProjectSummary(BaseModel):
    name: str


class ResolveProjectManagerFolderSummary(BaseModel):
    name: str


class ResolveProjectManagerFolderListData(BaseModel):
    folder: ResolveProjectManagerFolderSummary
    subfolders: list[ResolveProjectManagerFolderSummary] = Field(default_factory=list)
    projects: list[ResolveProjectSummary] = Field(default_factory=list)


class ResolveProjectManagerFolderStateData(BaseModel):
    folder: ResolveProjectManagerFolderSummary
    path: list[ResolveProjectManagerFolderSummary] = Field(default_factory=list)
    subfolders: list[ResolveProjectManagerFolderSummary] = Field(default_factory=list)
    projects: list[ResolveProjectSummary] = Field(default_factory=list)


class ResolveTimelineSummary(BaseModel):
    index: int
    name: str


class ResolveTimelineCurrentData(BaseModel):
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary


class ResolveTimelineCreateEmptyData(BaseModel):
    created: bool
    timeline: ResolveTimelineSummary


class ResolveTimelineSetCurrentData(BaseModel):
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary


class ResolveMediaPoolFolderSummary(BaseModel):
    name: str


class ResolveMediaPoolSubfolderSummary(BaseModel):
    name: str


class ResolveMediaClipSummary(BaseModel):
    name: str


class ResolveMediaClipDetail(BaseModel):
    name: str
    properties: dict[str, str] = Field(default_factory=dict)


class ResolveMediaPoolListData(BaseModel):
    folder: ResolveMediaPoolFolderSummary
    subfolders: list[ResolveMediaPoolSubfolderSummary] = Field(default_factory=list)
    clips: list[ResolveMediaClipSummary] = Field(default_factory=list)


class ResolveMediaPoolFolderStateData(BaseModel):
    folder: ResolveMediaPoolFolderSummary
    path: list[ResolveMediaPoolFolderSummary] = Field(default_factory=list)
    subfolders: list[ResolveMediaPoolSubfolderSummary] = Field(default_factory=list)
    clips: list[ResolveMediaClipSummary] = Field(default_factory=list)


class ResolveMediaPoolFolderNode(BaseModel):
    name: str
    clips: list[ResolveMediaClipSummary] = Field(default_factory=list)
    subfolders: list["ResolveMediaPoolFolderNode"] = Field(default_factory=list)


class ResolveMediaPoolFolderRecursiveData(BaseModel):
    folder: ResolveMediaPoolFolderSummary
    path: list[ResolveMediaPoolFolderSummary] = Field(default_factory=list)
    max_depth: int | None = None
    tree: ResolveMediaPoolFolderNode


class ResolveMediaImportData(BaseModel):
    imported_count: int
    items: list[ResolveMediaClipSummary] = Field(default_factory=list)


class ResolveTimelineAppendClipsData(BaseModel):
    timeline: ResolveTimelineSummary
    appended: bool
    count: int
    clip_names: list[str] = Field(default_factory=list)


class ResolveTimelineCreateFromClipsData(BaseModel):
    created: bool
    timeline: ResolveTimelineSummary
    count: int
    clip_names: list[str] = Field(default_factory=list)


class ResolveTimelineBuildFromPathsData(BaseModel):
    created: bool
    timeline: ResolveTimelineSummary
    imported_count: int
    count: int
    paths: list[str] = Field(default_factory=list)
    clip_names: list[str] = Field(default_factory=list)


class ResolveTimelineItemSummary(BaseModel):
    name: str
    start_frame: int | None = None
    end_frame: int | None = None
    item_index: int | None = None


class ResolveTimelineTrackSummary(BaseModel):
    track_type: str
    track_index: int
    items: list[ResolveTimelineItemSummary] = Field(default_factory=list)


class ResolveTimelineItemsListData(BaseModel):
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary
    tracks: list[ResolveTimelineTrackSummary] = Field(default_factory=list)


class ResolveTimelineTrackItemsData(BaseModel):
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary
    track: ResolveTimelineTrackSummary


class ResolveTimelineTrackInspectData(BaseModel):
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary
    track_type: str
    track_index: int
    item_count: int
    start_frame: int | None = None
    end_frame: int | None = None


class ResolveTimelineInspectData(BaseModel):
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary
    video_track_count: int
    audio_track_count: int
    video_item_count: int
    audio_item_count: int
    marker_count: int


class ResolveMarkerSummary(BaseModel):
    frame: int
    color: str | None = None
    name: str | None = None
    note: str | None = None
    duration: int | None = None
    custom_data: str | None = None


class ResolveMarkerAddData(BaseModel):
    added: bool
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary
    marker: ResolveMarkerSummary


class ResolveMarkerListData(BaseModel):
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary
    markers: list[ResolveMarkerSummary] = Field(default_factory=list)


class ResolveMarkerInspectData(BaseModel):
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary
    marker: ResolveMarkerSummary


class ResolveMarkerRangeListData(BaseModel):
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary
    frame_from: int | None = None
    frame_to: int | None = None
    markers: list[ResolveMarkerSummary] = Field(default_factory=list)


class ResolveMarkerDeleteMarkerData(BaseModel):
    frame: int


class ResolveMarkerDeleteData(BaseModel):
    deleted: bool
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary
    marker: ResolveMarkerDeleteMarkerData


class ResolveMediaClipInspectData(BaseModel):
    folder: ResolveMediaPoolFolderSummary
    clip: ResolveMediaClipDetail


class ResolveMediaClipInspectPathData(BaseModel):
    folder: ResolveMediaPoolFolderSummary
    path: list[ResolveMediaPoolFolderSummary] = Field(default_factory=list)
    clip: ResolveMediaClipDetail


class ResolveHealthData(BaseModel):
    """Structured response for the first health tool."""

    bridge: ResolveBridgeStatus
    executor: ResolveExecutorStatus
    resolve: ResolveAppStatus
    project: ResolveProjectStatus


class ResolveProjectCurrentData(BaseModel):
    project: ResolveProjectStatus


class ResolveProjectOpenData(BaseModel):
    opened: bool
    project: ResolveProjectStatus


class ResolveProjectListData(BaseModel):
    projects: list[ResolveProjectSummary] = Field(default_factory=list)


class ResolveTimelineListData(BaseModel):
    project: ResolveProjectStatus
    timelines: list[ResolveTimelineSummary] = Field(default_factory=list)


class ResolveTimelineClipPlacement(BaseModel):
    clip_name: str
    record_frame: int
    track_index: int = 1
    media_type: int = 1
    start_frame: int | None = None
    end_frame: int | None = None


class ResolveTimelinePlacedItemData(BaseModel):
    item_index: int | None = None
    name: str
    track_type: str
    track_index: int
    start_frame: int | None = None
    end_frame: int | None = None


class ResolveTimelineClipsPlaceData(BaseModel):
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary
    placed_count: int
    items: list[ResolveTimelinePlacedItemData] = Field(default_factory=list)


class ResolveTimelineItemInspectData(BaseModel):
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary
    item: ResolveTimelinePlacedItemData
    duration: int | None = None
    source_start_frame: int | None = None
    source_end_frame: int | None = None
    left_offset: int | None = None
    right_offset: int | None = None


class ResolveTimelineItemDeleteData(BaseModel):
    deleted: bool
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary
    item: ResolveTimelinePlacedItemData
    ripple: bool = False


class ResolveTimelineItemMoveData(BaseModel):
    moved: bool
    project: ResolveProjectStatus
    timeline: ResolveTimelineSummary
    source_item: ResolveTimelinePlacedItemData
    item: ResolveTimelinePlacedItemData


class ToolResultEnvelope(BaseModel):
    """Backend-friendly result for tools."""

    success: bool
    data: dict[str, Any] | None = None
    error: BridgeError | None = None
    warnings: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


MediaArtifactKind = Literal["json", "image", "audio", "text"]
MediaScreenshotKind = Literal["midpoint", "boundary", "peak_motion"]
MediaSegmentSource = Literal["speech", "audio_event", "scene", "fixed_window"]
TranscriptStatus = Literal["ok", "no_speech_detected", "low_confidence"]
VideoSegmentMode = Literal["shots", "fixed_window"]
VideoSegmentationMode = Literal["speech", "visual", "audio_visual"]


class MediaAnalysisArtifact(BaseModel):
    kind: MediaArtifactKind
    path: str
    label: str


class MediaAnalysisManifest(BaseModel):
    tool_name: str
    source: str
    analysis_id: str
    artifacts_dir: str
    created_at: str
    input_params: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[MediaAnalysisArtifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MediaSegmentScreenshot(BaseModel):
    path: str
    timestamp_sec: float
    kind: MediaScreenshotKind


class AudioFeatureFlags(BaseModel):
    speech_detected: bool
    music_detected: bool
    silence: bool
    energy: float


class VideoFeatureFlags(BaseModel):
    scene_change: bool
    motion_score: float
    black_frame_ratio: float


class SegmentTimeRange(BaseModel):
    start: float
    end: float


class AudioProbeMediaData(BaseModel):
    duration_sec: float
    sample_rate: int
    channels: int
    codec: str
    bit_rate: int


class AudioProbeAudioData(BaseModel):
    has_audio: bool
    speech_likelihood: float
    silence_ratio: float


class AudioTranscriptionSegment(BaseModel):
    start: float
    end: float
    text: str
    confidence: float | None = None
    segment_source: Literal["speech"] = "speech"
    track_index: int | None = None
    screenshot_path: str | None = None


class TranscriptSidecarSegment(BaseModel):
    start: float
    end: float
    text: str
    confidence: float | None = None
    track_index: int | None = None
    screenshot_path: str | None = None


class TranscriptSidecarEngine(BaseModel):
    name: str
    model: str
    device: str
    compute_type: str


class TranscriptSidecarData(BaseModel):
    source: str
    created_at: str
    engine: TranscriptSidecarEngine
    language: str | None = None
    duration_sec: float = 0.0
    transcript_status: TranscriptStatus
    segments: list[TranscriptSidecarSegment] = Field(default_factory=list)


class AudioEventSummary(BaseModel):
    start: float
    end: float
    event_type: Literal["silence", "music_like", "noise", "impact", "high_energy", "low_energy"]
    energy: float
    label: str


class AudioAnalysisSummary(BaseModel):
    speech_detected: bool
    music_detected: bool
    silence_ranges_count: int


class VideoProbeMediaData(BaseModel):
    duration_sec: float
    fps: float
    width: int
    height: int
    video_codec: str
    audio_codec: str | None = None


class VideoProbeTracksData(BaseModel):
    has_video: bool
    has_audio: bool


class VideoShotSummary(BaseModel):
    shot_index: int
    start: float
    end: float
    segment_source: Literal["scene"]
    visual_features: VideoFeatureFlags


class MediaSegmentSummary(BaseModel):
    segment_index: int | None = None
    start: float
    end: float
    segment_source: MediaSegmentSource | None = None
    text: str | None = None
    transcript: str | None = None
    audio_event: str | None = None
    audio_features: AudioFeatureFlags | None = None
    visual_features: VideoFeatureFlags | None = None
    track_index: int | None = None
    screenshot_path: str | None = None
    source_track_indexes: list[int] = Field(default_factory=list)
    screenshots: list[MediaSegmentScreenshot] = Field(default_factory=list)


class SegmentScreenshotSummary(BaseModel):
    start: float
    end: float
    screenshots: list[MediaSegmentScreenshot] = Field(default_factory=list)


class BaseMediaAnalysisData(BaseModel):
    source: str
    analysis_id: str
    artifacts_dir: str
    artifacts: list[MediaAnalysisArtifact] = Field(default_factory=list)


class AudioProbeData(BaseMediaAnalysisData):
    media: AudioProbeMediaData
    audio: AudioProbeAudioData


class AudioTranscriptionData(BaseMediaAnalysisData):
    transcript_status: TranscriptStatus
    segments: list[AudioTranscriptionSegment] = Field(default_factory=list)


class AudioEventsData(BaseMediaAnalysisData):
    events: list[AudioEventSummary] = Field(default_factory=list)
    summary: AudioAnalysisSummary


class VideoProbeData(BaseMediaAnalysisData):
    media: VideoProbeMediaData
    tracks: VideoProbeTracksData


class VideoShotsData(BaseMediaAnalysisData):
    shots: list[VideoShotSummary] = Field(default_factory=list)


class VideoSegmentScreenshotsData(BaseMediaAnalysisData):
    segments: list[SegmentScreenshotSummary] = Field(default_factory=list)


class VideoSegmentationData(BaseMediaAnalysisData):
    segmentation_mode: VideoSegmentationMode
    transcript_status: TranscriptStatus | None = None
    segments: list[MediaSegmentSummary] = Field(default_factory=list)
