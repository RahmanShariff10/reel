"""Pipeline stage implementation for Stage 1: Ingest."""

from __future__ import annotations

import typing
from pathlib import Path

from reel.common.logging import get_logger
from reel.common.models import Meta, is_valid, read_model, write_model
from reel.ingest.probe import extract_audio, probe_video

if typing.TYPE_CHECKING:
    from reel.jobs.pipeline import PipelineContext, ProgressCallback

log = get_logger("ingest.stage")


def is_valid_ingest(ctx: PipelineContext) -> bool:
    """Check whether the ingest stage output files exist and are valid.

    If the video has audio, both meta.json and audio.wav must exist and be valid.
    If the video has no audio (has_audio=False), meta.json alone suffices.
    """
    paths = ctx.paths
    if not is_valid(paths.meta_json, Meta):
        return False

    meta = read_model(paths.meta_json, Meta)
    if meta.has_audio:
        return paths.audio_wav.is_file() and paths.audio_wav.stat().st_size > 0

    return True


def run_ingest(
    ctx: PipelineContext,
    progress_cb: ProgressCallback | None = None,
) -> None:
    """Execute the ingest stage: inspect video metadata and extract audio.

    For local_path jobs, the input file is read in place and is never copied
    into the job directory.

    Raises
    ------
    ValueError
        If the input file does not exist or is not a valid video file.
    """
    input_file: Path | None = None
    if ctx.input_path and Path(ctx.input_path).is_file():
        input_file = Path(ctx.input_path)
    elif ctx.paths.input_file.is_file():
        input_file = ctx.paths.input_file

    if not input_file or not input_file.is_file():
        raise ValueError("Not a valid video file")

    log.info("Probing video metadata for job %s from %s", ctx.job_id, input_file)
    meta = probe_video(input_file)
    write_model(ctx.paths.meta_json, meta)

    if progress_cb:
        progress_cb(0.5)

    if meta.has_audio:
        sample_rate = ctx.config.ingest.audio_sample_rate
        log.info(
            "Extracting audio at %d Hz mono to %s",
            sample_rate,
            ctx.paths.audio_wav.name,
        )
        extract_audio(input_file, ctx.paths.audio_wav, sample_rate=sample_rate)
    else:
        log.info("Input video has no audio stream; skipping audio extraction")

    if progress_cb:
        progress_cb(1.0)
