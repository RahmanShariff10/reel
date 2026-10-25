"""Common Pydantic data models and atomic serialization helpers for Reel.

Every stage file listed in ARCHITECTURE.md has a corresponding model here.
These models form the data contract across all pipeline modules.
"""

from __future__ import annotations

import csv
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Stage 1: Ingest
# ---------------------------------------------------------------------------


class Meta(BaseModel):
    """Video metadata extracted during the ingest stage (written to meta.json)."""

    model_config = ConfigDict(extra="ignore")

    duration_s: float = Field(..., ge=0, description="Video duration in seconds")
    width: int = Field(..., gt=0, description="Frame width in pixels")
    height: int = Field(..., gt=0, description="Frame height in pixels")
    fps: float = Field(..., gt=0, description="Video frame rate")
    video_codec: str | None = Field(default=None, description="Video codec name")
    audio_codec: str | None = Field(default=None, description="Audio codec name")
    audio_sample_rate: int | None = Field(default=None, gt=0, description="Audio sample rate (Hz)")
    audio_channels: int | None = Field(default=None, gt=0, description="Number of audio channels")
    has_audio: bool = Field(default=True, description="Whether an audio stream is present")
    size_bytes: int | None = Field(default=None, ge=0, description="File size in bytes")


# ---------------------------------------------------------------------------
# Stage 2: Locate Scorebox
# ---------------------------------------------------------------------------


class Scorebox(BaseModel):
    """Score box location and sample detection (written to scorebox.json)."""

    model_config = ConfigDict(extra="ignore")

    found: bool = Field(..., description="Whether a valid score box was detected")
    box: list[int] | None = Field(
        default=None,
        description="Bounding box [x, y, w, h] in source video pixels",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Detection confidence score between 0 and 1",
    )
    sample_reading: str | None = Field(
        default=None,
        description="Sample score reading text extracted from candidate frames",
    )
    sample_time_s: float | None = Field(
        default=None,
        ge=0,
        description="Video time (seconds) of the frame the sample reading came from",
    )
    order: Literal["runs-wickets", "wickets-runs"] | None = Field(
        default=None,
        description="Order of the two score numbers on screen",
    )
    preview_url: str | None = Field(
        default=None,
        description="Relative URL to the score box preview image",
    )


# ---------------------------------------------------------------------------
# Stage 3 & 5: Scan & Classify Shots
# ---------------------------------------------------------------------------

ShotLabel = Literal["run_up", "close_up", "crowd", "field", "graphic"]


class Shot(BaseModel):
    """Camera shot boundary and classification label (element of shots.json)."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(..., description="0-indexed sequential shot identifier")
    start_s: float = Field(..., ge=0, description="Shot start time in seconds")
    end_s: float = Field(..., ge=0, description="Shot end time in seconds")
    duration_s: float | None = Field(
        default=None,
        ge=0,
        description="Shot duration in seconds",
    )
    keyframe_path: str | None = Field(
        default=None,
        description="Relative path to keyframe image",
    )
    label: ShotLabel | None = Field(
        default=None,
        description="Predicted camera shot type",
    )
    probabilities: dict[str, float] | None = Field(
        default=None,
        description="Per-class predicted probability distribution",
    )


# ---------------------------------------------------------------------------
# Stage 4: Read Score
# ---------------------------------------------------------------------------


class ScoreReading(BaseModel):
    """Raw OCR reading for a score crop (element of score_readings.json)."""

    model_config = ConfigDict(extra="ignore")

    time_s: float = Field(..., ge=0, description="Video timestamp in seconds")
    raw_text: str = Field(default="", description="Raw OCR recognised text")
    team: str | None = Field(default=None, description="Team abbreviation shown, e.g. 'IND'")
    runs: int | None = Field(default=None, ge=0, description="Parsed runs total")
    wickets: int | None = Field(default=None, ge=0, le=10, description="Parsed wickets lost")
    overs: float | None = Field(default=None, ge=0, description="Parsed overs bowled")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="OCR confidence score")
    visible: bool = Field(default=True, description="Whether score box is visible in this frame")


class ScoreTimelineEntry(BaseModel):
    """Validated match state at a given second (element of score_timeline.json)."""

    model_config = ConfigDict(extra="ignore")

    time_s: float = Field(..., ge=0, description="Timestamp in seconds")
    runs: int = Field(0, ge=0, description="Validated match runs")
    wickets: int = Field(0, ge=0, le=10, description="Validated match wickets")
    overs: float = Field(0.0, ge=0.0, description="Validated overs bowled")
    visible: bool = Field(default=True, description="Score graphic visibility")
    innings: int = Field(default=1, ge=1, le=2, description="Innings number (1 or 2)")


ScoreEventType = Literal["runs", "wicket", "wicket_overturned", "innings_start"]


class ScoreEvent(BaseModel):
    """Discrete match event emitted by state machine (element of score_events.json)."""

    model_config = ConfigDict(extra="ignore")

    type: ScoreEventType = Field(..., description="Event type emitted")
    time_s: float = Field(..., ge=0, description="Timestamp in seconds")
    runs_delta: int = Field(default=0, description="Change in runs (e.g. 4, 6)")
    wicket_delta: int = Field(default=0, description="Change in wickets (+1 or -1)")
    runs: int | None = Field(default=None, ge=0, description="Total runs after event")
    wickets: int | None = Field(default=None, ge=0, le=10, description="Total wickets after event")
    overs: float | None = Field(default=None, ge=0.0, description="Overs after event")
    innings: int = Field(default=1, ge=1, le=2, description="Innings number")
    overturned: bool = Field(default=False, description="Wicket later overturned on review")


# ---------------------------------------------------------------------------
# Stage 6: Audio Excitement
# ---------------------------------------------------------------------------


class ExcitementEntry(BaseModel):
    """Per-second excitement entry for excitement.csv."""

    model_config = ConfigDict(extra="ignore")

    second: int = Field(..., ge=0, description="Second offset within the video")
    excitement: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Combined excitement score in [0, 1]",
    )


# ---------------------------------------------------------------------------
# Stage 7: Deliveries
# ---------------------------------------------------------------------------


class Delivery(BaseModel):
    """A detected ball delivery segment (element of deliveries.json)."""

    model_config = ConfigDict(extra="ignore")

    id: str | int = Field(..., description="Unique delivery identifier")
    innings: int = Field(default=1, ge=1, le=2, description="Innings number (1 or 2)")
    over_ball: str | None = Field(
        default=None,
        description="Over and ball string (e.g. '16.2')",
    )
    start_s: float = Field(..., ge=0, description="Delivery start time (run-up start) in seconds")
    t_hit_s: float | None = Field(
        default=None,
        ge=0,
        description="Delivery hit/release time in seconds",
    )
    end_s: float = Field(..., ge=0, description="Delivery end time in seconds")
    runs_delta: int = Field(default=0, ge=0, description="Runs scored on this ball")
    wicket: bool = Field(default=False, description="Whether a wicket fell on this ball")
    overturned: bool = Field(default=False, description="Whether wicket was overturned on DRS")
    score_after: str | None = Field(
        default=None,
        description="Score text after delivery (e.g. 'IND 151/3')",
    )
    replay_count: int = Field(default=0, ge=0, description="Count of replays detected for ball")
    excitement_max: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Peak crowd excitement during delivery window",
    )


# ---------------------------------------------------------------------------
# Stage 8: Highlights & Events
# ---------------------------------------------------------------------------


class Reason(BaseModel):
    """Explanation factor for why a clip/event was selected."""

    model_config = ConfigDict(extra="ignore")

    signal: str = Field(..., description="Signal source: score, excitement, replays, match")
    value: Any = Field(..., description="Raw signal value")
    label: str = Field(..., description="Human-readable reason label (e.g. 'score +6')")


class ClipBoundary(BaseModel):
    """Start and end bounds of a clip in source seconds."""

    model_config = ConfigDict(extra="ignore")

    start_s: float = Field(..., ge=0, description="Clip start timestamp in seconds")
    end_s: float = Field(..., ge=0, description="Clip end timestamp in seconds")


EventType = Literal["wicket", "six", "four", "near_miss", "moment"]


class Event(BaseModel):
    """Highlight event returned by GET /api/jobs/{id}/result (in events.json)."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique event identifier (e.g. 'ev-01')")
    delivery_id: str | int | None = Field(default=None, description="Linked delivery identifier")
    type: EventType = Field(..., description="Event type")
    innings: int | None = Field(default=None, ge=1, le=2, description="Innings number")
    over_ball: str | None = Field(default=None, description="Over and ball string (e.g. '16.2')")
    score_text: str | None = Field(default=None, description="Score display text")
    importance: float = Field(..., ge=0.0, le=1.0, description="Computed importance score")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    reasons: list[Reason] = Field(default_factory=list, description="List of reasons for rating")
    moment_s: float = Field(..., ge=0, description="Timestamp of the key moment in seconds")
    clip: ClipBoundary = Field(..., description="Computed clip boundaries")


class ReelClip(BaseModel):
    """A clip specification in the reel assembly plan."""

    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(..., description="Identifier of the associated Event")
    start_s: float = Field(..., ge=0, description="Start timestamp in source video (seconds)")
    end_s: float = Field(..., ge=0, description="End timestamp in source video (seconds)")
    duration_s: float = Field(..., ge=0, description="Clip duration in seconds")
    caption: str | None = Field(default=None, description="Caption text drawn on the clip")
    offset_s: float = Field(default=0.0, ge=0, description="Start offset within the final reel")


class ReelPlan(BaseModel):
    """Reel assembly plan (written to reel_plan_<mode>.json)."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(..., description="Reel mode: '3min', '5min', '10min', 'all'")
    duration_s: float = Field(..., ge=0, description="Total expected reel duration in seconds")
    clips: list[ReelClip] = Field(default_factory=list, description="Ordered list of clips")


# ---------------------------------------------------------------------------
# Stage 9: Render & Summary
# ---------------------------------------------------------------------------


class InningsSummary(BaseModel):
    """Per-innings match statistics."""

    model_config = ConfigDict(extra="ignore")

    runs: int = Field(default=0, ge=0)
    wickets: int = Field(default=0, ge=0, le=10)
    overs: float | str = Field(default=0.0)
    fours: int = Field(default=0, ge=0)
    sixes: int = Field(default=0, ge=0)


class Summary(BaseModel):
    """High-level summary of processed match (written to summary.json)."""

    model_config = ConfigDict(extra="ignore")

    teams: list[str] | None = Field(default=None, description="Team names if detected")
    innings: list[InningsSummary] = Field(default_factory=list, description="Per-innings stats")
    deliveries_found: int = Field(default=0, ge=0, description="Total deliveries detected")
    processing_s: float = Field(default=0.0, ge=0, description="Total pipeline run time in seconds")
    scorebox_found: bool = Field(default=False, description="Whether score box was located")


# ---------------------------------------------------------------------------
# Atomic File IO and Model Helpers
# ---------------------------------------------------------------------------


def write_model(path: str | Path, model: Any) -> Path:
    """Serialize any Pydantic model (or list of models) atomically to JSON.

    Writes to a temporary file in the same directory first, then renames it.
    If an error occurs mid-write, the temporary file is deleted and the target
    path is never left in a corrupt or partial state.

    Parameters
    ----------
    path : str | Path
        Target destination file path.
    model : Any
        Pydantic BaseModel instance or sequence of models.

    Returns
    -------
    Path
        The written destination path.
    """
    dest = Path(path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    adapter: TypeAdapter[Any] = TypeAdapter(type(model))
    json_bytes = adapter.dump_json(model, indent=2)

    temp_file = tempfile.NamedTemporaryFile(
        dir=dest.parent,
        prefix=f".{dest.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(temp_file.name)

    try:
        temp_file.write(json_bytes)
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_file.close()
        temp_path.replace(dest)
    except Exception:
        temp_file.close()
        if temp_path.exists():
            temp_path.unlink()
        raise

    return dest


def read_model(path: str | Path, model_cls: type[T]) -> T:
    """Read and validate a Pydantic model or collection from a JSON file.

    Parameters
    ----------
    path : str | Path
        Path to JSON file.
    model_cls : type[T]
        Pydantic model class or type expression (e.g. ``list[Event]``).

    Returns
    -------
    T
        Validated model instance.
    """
    src = Path(path).resolve()
    content = src.read_bytes()
    adapter: TypeAdapter[T] = TypeAdapter(model_cls)
    return adapter.validate_json(content)


def is_valid(path: str | Path, model_cls: type[T]) -> bool:
    """Check whether a file exists and parses as a valid model without raising.

    Parameters
    ----------
    path : str | Path
        Path to inspect.
    model_cls : type[T]
        Target model class.

    Returns
    -------
    bool
        True if the file exists and passes validation; False otherwise.
    """
    p = Path(path)
    if not p.is_file():
        return False
    try:
        read_model(p, model_cls)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Excitement CSV Helpers
# ---------------------------------------------------------------------------


def write_excitement_csv(
    path: str | Path,
    series: Sequence[float | ExcitementEntry | dict[str, Any]],
) -> Path:
    """Write excitement values to CSV with exactly one row per second.

    Parameters
    ----------
    path : str | Path
        Target CSV file path.
    series : Sequence[float | ExcitementEntry | dict[str, Any]]
        Sequence of excitement values. Can be floats (where index = second),
        ExcitementEntry instances, or dictionaries with 'second' and 'excitement'.

    Returns
    -------
    Path
        The written CSV destination path.
    """
    dest = Path(path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    temp_file = tempfile.NamedTemporaryFile(
        dir=dest.parent,
        prefix=f".{dest.name}.",
        suffix=".tmp",
        delete=False,
        mode="w",
        newline="",
    )
    temp_path = Path(temp_file.name)

    try:
        writer = csv.writer(temp_file)
        writer.writerow(["second", "excitement"])

        for i, item in enumerate(series):
            if isinstance(item, (int, float)):
                sec = i
                val = float(item)
            elif isinstance(item, ExcitementEntry):
                sec = item.second
                val = float(item.excitement)
            elif isinstance(item, dict):
                sec = int(item.get("second", i))
                val = float(item["excitement"])
            else:
                raise TypeError(f"Unsupported excitement element type: {type(item)}")

            writer.writerow([sec, f"{val:.6f}"])

        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_file.close()
        temp_path.replace(dest)
    except Exception:
        temp_file.close()
        if temp_path.exists():
            temp_path.unlink()
        raise

    return dest


def read_excitement_csv(path: str | Path) -> list[float]:
    """Read excitement values from CSV into a list of floats (index = second).

    Parameters
    ----------
    path : str | Path
        Path to CSV file.

    Returns
    -------
    list[float]
        Excitement scores in second order.
    """
    src = Path(path).resolve()
    with open(src, newline="") as fh:
        reader = csv.reader(fh)
        rows = list(reader)

    if not rows:
        return []

    # Skip header if present
    start_idx = 1 if rows[0] and rows[0][0].lower().startswith("sec") else 0

    values: list[float] = []
    for row in rows[start_idx:]:
        if not row:
            continue
        # Format is second, excitement
        val = float(row[1]) if len(row) > 1 else float(row[0])
        values.append(val)

    return values


def read_excitement_entries(path: str | Path) -> list[ExcitementEntry]:
    """Read excitement entries into a list of ExcitementEntry models."""
    src = Path(path).resolve()
    with open(src, newline="") as fh:
        reader = csv.reader(fh)
        rows = list(reader)

    if not rows:
        return []

    start_idx = 1 if rows[0] and rows[0][0].lower().startswith("sec") else 0
    entries: list[ExcitementEntry] = []
    for i, row in enumerate(rows[start_idx:]):
        if not row:
            continue
        sec = int(row[0]) if len(row) > 1 else i
        val = float(row[1]) if len(row) > 1 else float(row[0])
        entries.append(ExcitementEntry(second=sec, excitement=val))

    return entries
