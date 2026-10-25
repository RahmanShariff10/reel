"""Render the clips of a reel plan (first half of stage 9, ``render``).

Each clip is cut with frame-accurate seeking and re-encoded to the output resolution
(H.264 yuv420p + AAC, uniform settings so clips can later be joined without
re-encoding). A caption is drawn bottom-left on a semi-transparent bar with the
bundled Inter Bold font (SIL Open Font License, ``backend/assets/fonts``), and the clip
fades in and out. Sources without audio get a silent track.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from reel.common.config import RenderConfig
from reel.common.logging import get_logger
from reel.common.models import ReelClip, ReelPlan
from reel.ingest.probe import find_binary

log = get_logger("render.clips")

FONT = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "Inter-Bold.ttf"


def _escape(path: Path) -> str:
    """Escape a path for use inside an ffmpeg filter argument."""
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def encode_args(cfg: RenderConfig, fps: float) -> list[str]:
    """Output encoding shared by every reel part (clips and title card)."""
    return [
        "-c:v",
        cfg.codec,
        "-preset",
        cfg.preset,
        "-crf",
        str(cfg.crf),
        "-pix_fmt",
        "yuv420p",
        "-r",
        f"{fps:g}",
        "-c:a",
        cfg.audio_codec,
        "-b:a",
        cfg.audio_bitrate,
        "-ar",
        str(cfg.audio_rate),
        "-ac",
        "2",
        "-video_track_timescale",
        "12800",
    ]


def scale_filter(cfg: RenderConfig) -> str:
    w, h = cfg.output_resolution
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )


def caption_bottom(
    cfg: RenderConfig, src_size: tuple[int, int], avoid_box: list[int] | None
) -> int:
    """Distance (output px) from the frame bottom to the caption's bottom edge.

    Normally a small margin; raised above ``avoid_box`` (e.g. the broadcast's own score
    box, in source pixels) when the caption would otherwise cover it.
    """
    out_w, out_h = cfg.output_resolution
    margin = round(out_h * 0.06)
    if not avoid_box:
        return margin
    sw, sh = src_size
    scale = min(out_w / sw, out_h / sh)
    pad_y = (out_h - sh * scale) / 2
    x, y, w, h = avoid_box
    box_left, box_top, box_bottom = x * scale, y * scale + pad_y, (y + h) * scale + pad_y
    caption_top = out_h - margin - cfg.caption_font_size * 2
    caption_right = out_w * 0.6
    overlaps = box_left < caption_right and box_bottom > caption_top
    return round(out_h - box_top + margin / 2) if overlaps else margin


def render_clip(
    video: Path,
    clip: ReelClip,
    out: Path,
    cfg: RenderConfig,
    fps: float,
    has_audio: bool,
    bottom_px: int | None = None,
) -> Path:
    dur = clip.end_s - clip.start_s
    fade = min(cfg.fade_duration_s, dur / 4)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        vf = [scale_filter(cfg)]
        if clip.caption:
            text_file = Path(tmp) / "caption.txt"
            text_file.write_text(clip.caption, encoding="utf-8")
            margin = round(cfg.output_resolution[1] * 0.06)
            bottom = margin if bottom_px is None else bottom_px
            vf.append(
                f"drawtext=fontfile='{_escape(FONT)}':textfile='{_escape(text_file)}'"
                f":fontsize={cfg.caption_font_size}:fontcolor=white"
                f":box=1:boxcolor=black@0.55:boxborderw={round(cfg.caption_font_size * 0.45)}"
                f":x={margin}:y=h-th-{bottom}"
            )
        vf.append(f"fade=t=in:st=0:d={fade:.3f},fade=t=out:st={dur - fade:.3f}:d={fade:.3f}")
        af = f"afade=t=in:st=0:d={fade:.3f},afade=t=out:st={dur - fade:.3f}:d={fade:.3f}"

        cmd = [
            find_binary("ffmpeg"),
            "-y",
            "-v",
            "error",
            "-ss",
            f"{clip.start_s:.3f}",
            "-i",
            str(video),
        ]
        if not has_audio:
            cmd += ["-f", "lavfi", "-i", f"anullsrc=r={cfg.audio_rate}:cl=stereo"]
        cmd += [
            "-t",
            f"{dur:.3f}",
            "-vf",
            ",".join(vf),
            "-af",
            af,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0" if has_audio else "1:a:0",
            *encode_args(cfg, fps),
            "-movflags",
            "+faststart",
            str(out),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError(f"Rendering clip {clip.event_id} failed: {proc.stderr.strip()}")
    return out


def render_clips(
    video: Path,
    plan: ReelPlan,
    clips_dir: Path,
    cfg: RenderConfig,
    fps: float,
    has_audio: bool,
    progress: Callable[[float], None] | None = None,
    bottom_px: int | None = None,
) -> list[Path]:
    """Render every clip of the plan to ``clips_dir/<event_id>.mp4``."""
    outputs = []
    for i, clip in enumerate(plan.clips):
        outputs.append(
            render_clip(
                video, clip, clips_dir / f"{clip.event_id}.mp4", cfg, fps, has_audio, bottom_px
            )
        )
        if progress:
            progress((i + 1) / len(plan.clips))
    log.info("Rendered %d clips", len(outputs))
    return outputs
