"""Video probing and audio extraction utilities using ffprobe and ffmpeg."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from reel.common.logging import get_logger
from reel.common.models import Meta

log = get_logger("ingest.probe")


def find_binary(name: str) -> str:
    """Find a system binary, checking PATH and common macOS / Linux locations."""
    path = shutil.which(name)
    if path:
        return path

    candidates = [
        Path("/opt/homebrew/bin") / name,
        Path("/usr/local/bin") / name,
        Path("/usr/bin") / name,
        Path(os.path.expanduser("~/.local/bin")) / name,
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)

    raise FileNotFoundError(
        f"Required binary '{name}' not found on PATH. Please install ffmpeg/ffprobe."
    )


def probe_video(video_path: Path | str) -> Meta:
    """Inspect a video file with ffprobe and return a validated Meta model.

    Raises
    ------
    ValueError
        If the file does not exist, cannot be decoded, or contains no video stream.
    """
    path = Path(video_path).resolve()
    if not path.is_file():
        raise ValueError("Not a valid video file")

    ffprobe = find_binary("ffprobe")
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,sample_rate,channels",
        "-of",
        "json",
        str(path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=30.0,
        )
    except Exception as exc:
        raise ValueError("Not a valid video file") from exc

    if proc.returncode != 0 or not proc.stdout.strip():
        raise ValueError("Not a valid video file")

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("Not a valid video file") from exc

    streams = data.get("streams", [])
    format_info = data.get("format", {})

    # Locate primary video stream
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video_stream:
        raise ValueError("Not a valid video file")

    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise ValueError("Not a valid video file")

    # Compute frame rate
    r_fps = video_stream.get("r_frame_rate", "0/0")
    avg_fps = video_stream.get("avg_frame_rate", "0/0")
    fps = 0.0
    for rate_str in (r_fps, avg_fps):
        try:
            val = float(Fraction(rate_str))
            if val > 0:
                fps = val
                break
        except (ValueError, ZeroDivisionError):
            continue

    if fps <= 0:
        fps = 25.0  # Fallback standard fps if undetectable

    # Duration
    duration_str = format_info.get("duration") or video_stream.get("duration")
    duration_s = float(duration_str) if duration_str is not None else 0.0

    # Size
    size_str = format_info.get("size")
    size_bytes = int(size_str) if size_str is not None else path.stat().st_size

    # Locate primary audio stream
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    has_audio = audio_stream is not None

    audio_codec: str | None = None
    audio_sample_rate: int | None = None
    audio_channels: int | None = None

    if audio_stream:
        audio_codec = audio_stream.get("codec_name")
        sr_val = audio_stream.get("sample_rate")
        audio_sample_rate = int(sr_val) if sr_val is not None else None
        ch_val = audio_stream.get("channels")
        audio_channels = int(ch_val) if ch_val is not None else None

    return Meta(
        duration_s=round(duration_s, 3),
        width=width,
        height=height,
        fps=round(fps, 3),
        video_codec=video_stream.get("codec_name"),
        audio_codec=audio_codec,
        audio_sample_rate=audio_sample_rate,
        audio_channels=audio_channels,
        has_audio=has_audio,
        size_bytes=size_bytes,
    )


def extract_audio(
    video_path: Path | str,
    out_wav_path: Path | str,
    sample_rate: int = 32000,
) -> Path:
    """Extract audio from video to 16-bit PCM WAV at the specified sample rate (mono).

    Parameters
    ----------
    video_path : Path | str
        Source video path.
    out_wav_path : Path | str
        Destination .wav path.
    sample_rate : int, optional
        Target sample rate in Hz (default: 32000).

    Returns
    -------
    Path
        Destination path of the extracted audio file.
    """
    vpath = Path(video_path).resolve()
    out_path = Path(out_wav_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = find_binary("ffmpeg")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(vpath),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        str(out_path),
    ]

    log.info("Extracting audio: %s -> %s", vpath.name, out_path.name)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=120.0,
    )

    if proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
        raise RuntimeError(f"Audio extraction failed: {proc.stderr}")

    return out_path
