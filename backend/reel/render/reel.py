"""Title card and final reel assembly (second half of stage 9, ``render``).

The title card (teams, innings scores, reel length) is drawn with Pillow and encoded as
a 3 s clip with exactly the clip settings, so the title and the event clips can be
joined with the ffmpeg concat demuxer without re-encoding. The reel is written to a
temporary file and renamed, so a failed re-render never replaces a good reel.
"""

from __future__ import annotations

import subprocess
import tempfile
import typing
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from reel.common.config import RenderConfig
from reel.common.logging import get_logger
from reel.common.models import (
    Delivery,
    InningsSummary,
    Meta,
    ReelPlan,
    Scorebox,
    Summary,
    is_valid,
    read_model,
    write_model,
)
from reel.ingest.probe import find_binary
from reel.render.clips import FONT, caption_bottom, encode_args, render_clips

if typing.TYPE_CHECKING:
    from reel.jobs.pipeline import PipelineContext, ProgressCallback

log = get_logger("render.reel")

MODE_LABEL = {
    "3min": "3-minute highlights",
    "5min": "5-minute highlights",
    "10min": "10-minute highlights",
    "all": "Every wicket and boundary",
}


def innings_lines(deliveries: list[Delivery]) -> tuple[list[str], list[str]]:
    """(teams, score lines) from the last known score of each innings."""
    teams: list[str] = []
    lines: list[str] = []
    for inn in (1, 2):
        scored = [d for d in deliveries if d.innings == inn and d.score_after]
        if not scored:
            continue
        last = max(scored, key=lambda d: d.start_s)
        team = last.score_after.split()[0] if " " in last.score_after else None
        if team:
            teams.append(team)
        overs = f" ({last.over_ball} ov)" if last.over_ball else ""
        lines.append(f"{last.score_after}{overs}")
    return teams, lines


def make_title(
    path: Path, teams: list[str], scores: list[str], mode: str, size: tuple[int, int]
) -> Path:
    w, h = size
    img = Image.new("RGB", size, (13, 27, 42))
    draw = ImageDraw.Draw(img)
    big = ImageFont.truetype(str(FONT), round(h * 0.1))
    mid = ImageFont.truetype(str(FONT), round(h * 0.055))
    small = ImageFont.truetype(str(FONT), round(h * 0.04))
    heading = " vs ".join(teams) if len(teams) >= 2 else "Match highlights"
    rows = [(heading, big, (255, 255, 255))]
    rows += [(s, mid, (220, 230, 240)) for s in scores]
    rows.append((MODE_LABEL.get(mode, mode), small, (150, 200, 120)))
    heights = [draw.textbbox((0, 0), t, font=f)[3] for t, f, _ in rows]
    gap = round(h * 0.04)
    y = (h - sum(heights) - gap * (len(rows) - 1)) / 2
    for (text, font, colour), th in zip(rows, heights):
        tw = draw.textlength(text, font=font)
        draw.text(((w - tw) / 2, y), text, font=font, fill=colour)
        y += th + gap
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def title_clip(png: Path, out: Path, seconds: float, cfg: RenderConfig, fps: float) -> Path:
    fade = min(cfg.fade_duration_s, seconds / 4)
    cmd = [
        find_binary("ffmpeg"),
        "-y",
        "-v",
        "error",
        "-loop",
        "1",
        "-framerate",
        f"{fps:g}",
        "-i",
        str(png),
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=r={cfg.audio_rate}:cl=stereo",
        "-t",
        f"{seconds:.3f}",
        "-vf",
        f"fade=t=out:st={seconds - fade:.3f}:d={fade:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        *encode_args(cfg, fps),
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Title card encoding failed: {proc.stderr.strip()}")
    return out


def concat(parts: list[Path], out: Path) -> Path:
    """Join same-encoded parts without re-encoding; replaces ``out`` only on success."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        listing = Path(tmp) / "parts.txt"
        listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
        partial = Path(tmp) / out.name
        proc = subprocess.run(
            [
                find_binary("ffmpeg"),
                "-y",
                "-v",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listing),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(partial),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0 or not partial.is_file():
            raise RuntimeError(f"Joining the reel failed: {proc.stderr.strip()}")
        partial.replace(out)
    return out


def _input_file(ctx: PipelineContext) -> Path:
    if ctx.input_path and Path(ctx.input_path).is_file():
        return Path(ctx.input_path)
    if ctx.paths.input_file.is_file():
        return ctx.paths.input_file
    raise ValueError("Not a valid video file")


def render_reel(
    ctx: PipelineContext, mode: str = "5min", progress_cb: ProgressCallback | None = None
) -> Path:
    """Render the clips, title card and final reel for a mode."""
    paths, cfg = ctx.paths, ctx.config.render
    meta = read_model(paths.meta_json, Meta)
    plan = read_model(paths.reel_plan_path(mode), ReelPlan)
    scorebox = read_model(paths.scorebox_json, Scorebox) if paths.scorebox_json.is_file() else None
    fps = float(round(meta.fps)) or 25.0
    bottom = caption_bottom(
        cfg, (meta.width, meta.height), scorebox.box if scorebox and scorebox.found else None
    )

    paths.clips_dir.mkdir(parents=True, exist_ok=True)  # also needed when there are no clips
    clips = render_clips(
        _input_file(ctx),
        plan,
        paths.clips_dir,
        cfg,
        fps,
        meta.has_audio,
        progress=(lambda f: progress_cb(0.9 * f)) if progress_cb else None,
        bottom_px=bottom,
    )
    deliveries = (
        read_model(paths.deliveries_json, list[Delivery]) if paths.deliveries_json.is_file() else []
    )
    teams, scores = innings_lines(deliveries)
    make_title(paths.title_png, teams, scores, mode, tuple(cfg.output_resolution))
    title = title_clip(
        paths.title_png,
        paths.clips_dir / "_title.mp4",
        ctx.config.highlights.title_card_s,
        cfg,
        fps,
    )
    out = concat([title, *clips], paths.reel_path(mode))
    log.info("Reel %s written: %d clips, plan %.1f s", out.name, len(clips), plan.duration_s)
    if progress_cb:
        progress_cb(1.0)
    return out


def is_valid_render(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    return (
        paths.reel_path("5min").is_file()
        and paths.title_png.is_file()
        and paths.clips_dir.is_dir()
        and is_valid(paths.reel_plan_path("5min"), ReelPlan)
        and is_valid(paths.summary_json, Summary)
    )


def basic_summary(deliveries: list[Delivery], scorebox_found: bool) -> Summary:
    """Match summary from deliveries (pipeline wiring adds processing times)."""
    teams, _ = innings_lines(deliveries)
    innings = []
    for inn in (1, 2):
        ds = [d for d in deliveries if d.innings == inn]
        if not ds:
            continue
        scored = [d for d in ds if d.score_after and "/" in d.score_after]
        runs = wickets = 0
        overs: float | str = 0.0
        if scored:
            last = max(scored, key=lambda d: d.start_s)
            runs, wickets = (int(x) for x in last.score_after.split()[-1].split("/"))
            overs = last.over_ball or 0.0
        innings.append(
            InningsSummary(
                runs=runs,
                wickets=min(wickets, 10),
                overs=overs,
                fours=sum(d.runs_delta == 4 for d in ds),
                sixes=sum(d.runs_delta == 6 for d in ds),
            )
        )
    return Summary(
        teams=teams or None,
        innings=innings,
        deliveries_found=len(deliveries),
        scorebox_found=scorebox_found,
    )


def run_render(ctx: PipelineContext, progress_cb: ProgressCallback | None = None) -> None:
    render_reel(ctx, "5min", progress_cb)
    paths = ctx.paths
    deliveries = (
        read_model(paths.deliveries_json, list[Delivery]) if paths.deliveries_json.is_file() else []
    )
    found = paths.scorebox_json.is_file() and read_model(paths.scorebox_json, Scorebox).found
    write_model(paths.summary_json, basic_summary(deliveries, found))
