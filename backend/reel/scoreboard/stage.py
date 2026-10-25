"""Pipeline stage 2: ``locate_scorebox``."""

from __future__ import annotations

import typing
from pathlib import Path

import cv2

from reel.common.logging import get_logger
from reel.common.models import Meta, Scorebox, is_valid, read_model, write_model
from reel.ingest.frames import grab_frame
from reel.scoreboard.locate import frame_reader, locate_scorebox

if typing.TYPE_CHECKING:
    from reel.jobs.pipeline import PipelineContext, ProgressCallback

log = get_logger("scoreboard.stage")


def _input_file(ctx: PipelineContext) -> Path:
    if ctx.input_path and Path(ctx.input_path).is_file():
        return Path(ctx.input_path)
    if ctx.paths.input_file.is_file():
        return ctx.paths.input_file
    raise ValueError("Not a valid video file")


def is_valid_locate_scorebox(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    return is_valid(paths.scorebox_json, Scorebox) and paths.scorebox_preview_jpg.is_file()


def run_locate_scorebox(
    ctx: PipelineContext,
    progress_cb: ProgressCallback | None = None,
) -> None:
    """Find the score box and write scorebox.json plus scorebox_preview.jpg.

    A missing score box never fails the job: it is recorded as ``found: false``.
    """
    paths = ctx.paths
    video = _input_file(ctx)
    meta = read_model(paths.meta_json, Meta)

    result = locate_scorebox(
        frame_reader(video, meta.width, meta.height),
        meta.duration_s,
        meta.width,
        meta.height,
        ctx.config.scoreboard,
        progress=(lambda f: progress_cb(0.95 * f)) if progress_cb else None,
    )

    preview_t = result.sample_time_s if result.sample_time_s is not None else meta.duration_s / 2
    frame = grab_frame(video, preview_t, meta.width, meta.height)
    if frame is None:
        raise RuntimeError(f"Could not read a preview frame at {preview_t:.1f}s")
    if result.found and result.box:
        x, y, w, h = result.box
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 220, 0), 3)
    if not cv2.imwrite(str(paths.scorebox_preview_jpg), frame):
        raise RuntimeError("Could not write scorebox_preview.jpg")

    write_model(
        paths.scorebox_json,
        Scorebox(
            found=result.found,
            box=list(result.box) if result.box else None,
            confidence=result.confidence,
            sample_reading=result.sample_reading,
            sample_time_s=result.sample_time_s,
            order=result.order,
            preview_url=f"/api/files/{ctx.job_id}/scorebox_preview.jpg",
        ),
    )
    log.info(
        "Score box %s for job %s (%d samples read)",
        f"found at {result.box}" if result.found else "not found",
        ctx.job_id,
        result.samples_read,
    )
    if progress_cb:
        progress_cb(1.0)
