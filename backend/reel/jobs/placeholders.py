"""Minimal valid placeholder implementations for all 9 pipeline stages.

Each placeholder produces minimal valid models and files that satisfy
slice-02 contracts, allowing end-to-end execution before real algorithms land.
"""

from __future__ import annotations

import typing

from reel.common.models import (
    ClipBoundary,
    Delivery,
    Event,
    InningsSummary,
    Meta,
    Reason,
    ReelClip,
    ReelPlan,
    Scorebox,
    ScoreEvent,
    ScoreReading,
    ScoreTimelineEntry,
    Shot,
    Summary,
    is_valid,
    read_model,
    write_excitement_csv,
    write_model,
)

if typing.TYPE_CHECKING:
    from reel.jobs.pipeline import PipelineContext


# Minimal 1x1 transparent PNG / JPEG bytes for preview / title cards
DUMMY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf"
    b"\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)

DUMMY_JPG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C"
    b"\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b"
    b"\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7)"
    b",01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff"
    b"\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00"
    b"\x00?\x00\xbf\x00\xff\xd9"
)

# Minimal WAV header bytes (PCM 16-bit, 32kHz, mono, 0.5s silence)
DUMMY_WAV_BYTES = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80}\x00\x00"
    b"\x00\xfa\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
)

DUMMY_MP4_BYTES = b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41\x00\x00\x00\x08free"


# ---------------------------------------------------------------------------
# Stage 1: Ingest
# ---------------------------------------------------------------------------


def is_valid_ingest(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    return is_valid(paths.meta_json, Meta) and paths.audio_wav.is_file()


def run_ingest(ctx: PipelineContext) -> None:
    paths = ctx.paths
    meta = Meta(
        duration_s=1200.0,
        width=1280,
        height=720,
        fps=25.0,
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=32000,
        audio_channels=1,
        size_bytes=50000000,
    )
    write_model(paths.meta_json, meta)
    paths.audio_wav.write_bytes(DUMMY_WAV_BYTES)


# ---------------------------------------------------------------------------
# Stage 2: Locate Scorebox
# ---------------------------------------------------------------------------


def is_valid_locate_scorebox(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    return is_valid(paths.scorebox_json, Scorebox) and paths.scorebox_preview_jpg.is_file()


def run_locate_scorebox(ctx: PipelineContext) -> None:
    paths = ctx.paths
    scorebox = Scorebox(
        found=True,
        box=[120, 650, 360, 42],
        confidence=0.94,
        sample_reading="IND 145/3  16.2 ov",
        preview_url=f"/api/files/{ctx.job_id}/scorebox_preview.jpg",
    )
    write_model(paths.scorebox_json, scorebox)
    paths.scorebox_preview_jpg.write_bytes(DUMMY_JPG_BYTES)


# ---------------------------------------------------------------------------
# Stage 3: Scan
# ---------------------------------------------------------------------------


def is_valid_scan(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    return (
        is_valid(paths.shots_json, list[Shot])
        and paths.keyframes_dir.is_dir()
        and paths.score_crops_dir.is_dir()
    )


def run_scan(ctx: PipelineContext) -> None:
    paths = ctx.paths
    paths.keyframes_dir.mkdir(parents=True, exist_ok=True)
    paths.score_crops_dir.mkdir(parents=True, exist_ok=True)

    shots = [
        Shot(id=0, start_s=0.0, end_s=6.0, duration_s=6.0, keyframe_path="keyframes/shot_0.jpg"),
        Shot(id=1, start_s=6.0, end_s=14.0, duration_s=8.0, keyframe_path="keyframes/shot_1.jpg"),
        Shot(id=2, start_s=14.0, end_s=22.0, duration_s=8.0, keyframe_path="keyframes/shot_2.jpg"),
    ]
    write_model(paths.shots_json, shots)

    (paths.keyframes_dir / "shot_0.jpg").write_bytes(DUMMY_JPG_BYTES)
    (paths.keyframes_dir / "shot_1.jpg").write_bytes(DUMMY_JPG_BYTES)
    (paths.score_crops_dir / "crop_0.jpg").write_bytes(DUMMY_JPG_BYTES)


# ---------------------------------------------------------------------------
# Stage 4: Read Score
# ---------------------------------------------------------------------------


def is_valid_read_score(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    return (
        is_valid(paths.score_readings_json, list[ScoreReading])
        and is_valid(paths.score_timeline_json, list[ScoreTimelineEntry])
        and is_valid(paths.score_events_json, list[ScoreEvent])
    )


def run_read_score(ctx: PipelineContext) -> None:
    paths = ctx.paths
    readings = [
        ScoreReading(
            time_s=6.0,
            raw_text="IND 145/3 16.2 ov",
            runs=145,
            wickets=3,
            overs=16.2,
            confidence=0.96,
            visible=True,
        ),
        ScoreReading(
            time_s=10.0,
            raw_text="IND 151/3 16.2 ov",
            runs=151,
            wickets=3,
            overs=16.2,
            confidence=0.97,
            visible=True,
        ),
    ]
    timeline = [
        ScoreTimelineEntry(time_s=0.0, runs=145, wickets=3, overs=16.1, visible=True, innings=1),
        ScoreTimelineEntry(time_s=6.0, runs=145, wickets=3, overs=16.2, visible=True, innings=1),
        ScoreTimelineEntry(time_s=10.0, runs=151, wickets=3, overs=16.2, visible=True, innings=1),
    ]
    events = [
        ScoreEvent(
            type="runs",
            time_s=8.0,
            runs_delta=6,
            wicket_delta=0,
            runs=151,
            wickets=3,
            overs=16.2,
            innings=1,
        )
    ]
    write_model(paths.score_readings_json, readings)
    write_model(paths.score_timeline_json, timeline)
    write_model(paths.score_events_json, events)


# ---------------------------------------------------------------------------
# Stage 5: Classify Shots
# ---------------------------------------------------------------------------


def is_valid_classify_shots(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    if not paths.shot_embeddings_npy.is_file():
        return False
    if not is_valid(paths.shots_json, list[Shot]):
        return False
    shots = read_model(paths.shots_json, list[Shot])
    # Must have label on at least one shot
    return any(s.label is not None for s in shots)


def run_classify_shots(ctx: PipelineContext) -> None:
    paths = ctx.paths
    paths.shot_embeddings_npy.write_bytes(b"DUMMY_NPY_EMBEDDINGS")

    shots = [
        Shot(
            id=0,
            start_s=0.0,
            end_s=6.0,
            duration_s=6.0,
            keyframe_path="keyframes/shot_0.jpg",
            label="run_up",
            probabilities={"run_up": 0.85, "field": 0.1, "close_up": 0.05},
        ),
        Shot(
            id=1,
            start_s=6.0,
            end_s=14.0,
            duration_s=8.0,
            keyframe_path="keyframes/shot_1.jpg",
            label="field",
            probabilities={"run_up": 0.05, "field": 0.85, "crowd": 0.1},
        ),
        Shot(
            id=2,
            start_s=14.0,
            end_s=22.0,
            duration_s=8.0,
            keyframe_path="keyframes/shot_2.jpg",
            label="crowd",
            probabilities={"crowd": 0.9, "close_up": 0.1},
        ),
    ]
    write_model(paths.shots_json, shots)


# ---------------------------------------------------------------------------
# Stage 6: Audio Excitement
# ---------------------------------------------------------------------------


def is_valid_audio(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    return paths.excitement_csv.is_file() and paths.excitement_csv.stat().st_size > 0


def run_audio(ctx: PipelineContext) -> None:
    paths = ctx.paths
    values = [0.10, 0.12, 0.15, 0.25, 0.55, 0.90, 0.88, 0.75, 0.50, 0.30]
    write_excitement_csv(paths.excitement_csv, values)


# ---------------------------------------------------------------------------
# Stage 7: Deliveries
# ---------------------------------------------------------------------------


def is_valid_deliveries(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    return is_valid(paths.deliveries_json, list[Delivery])


def run_deliveries(ctx: PipelineContext) -> None:
    paths = ctx.paths
    deliveries = [
        Delivery(
            id="del-01",
            innings=1,
            over_ball="16.2",
            start_s=0.0,
            t_hit_s=5.0,
            end_s=14.0,
            runs_delta=6,
            wicket=False,
            overturned=False,
            score_after="IND 151/3",
            replay_count=1,
            excitement_max=0.90,
        )
    ]
    write_model(paths.deliveries_json, deliveries)


# ---------------------------------------------------------------------------
# Stage 8: Highlights
# ---------------------------------------------------------------------------


def is_valid_highlights(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    return is_valid(paths.events_json, list[Event]) and is_valid(
        paths.reel_plan_path("5min"), ReelPlan
    )


def run_highlights(ctx: PipelineContext) -> None:
    paths = ctx.paths
    events = [
        Event(
            id="ev-01",
            delivery_id="del-01",
            type="six",
            innings=1,
            over_ball="16.2",
            score_text="IND 151/3",
            importance=0.92,
            confidence=0.96,
            reasons=[
                Reason(signal="score", value=6, label="score +6"),
                Reason(signal="excitement", value=0.90, label="crowd excitement high"),
                Reason(signal="replays", value=1, label="1 replay"),
            ],
            moment_s=5.0,
            clip=ClipBoundary(start_s=0.0, end_s=14.0),
        )
    ]
    plan = ReelPlan(
        mode="5min",
        duration_s=14.0,
        clips=[
            ReelClip(
                event_id="ev-01",
                start_s=0.0,
                end_s=14.0,
                duration_s=14.0,
                caption="SIX · 16.2 ov · IND 151/3",
                offset_s=0.0,
            )
        ],
    )
    write_model(paths.events_json, events)
    write_model(paths.reel_plan_path("5min"), plan)


# ---------------------------------------------------------------------------
# Stage 9: Render
# ---------------------------------------------------------------------------


def is_valid_render(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    return (
        paths.reel_path("5min").is_file()
        and paths.title_png.is_file()
        and paths.clips_dir.is_dir()
        and is_valid(paths.summary_json, Summary)
    )


def run_render(ctx: PipelineContext) -> None:
    paths = ctx.paths
    paths.clips_dir.mkdir(parents=True, exist_ok=True)
    paths.reel_path("5min").write_bytes(DUMMY_MP4_BYTES)
    paths.title_png.write_bytes(DUMMY_PNG_BYTES)
    (paths.clips_dir / "clip_ev-01.mp4").write_bytes(DUMMY_MP4_BYTES)

    summary = Summary(
        teams=["IND", "ENG"],
        innings=[
            InningsSummary(innings=1, runs=151, wickets=3, overs=16.2, fours=8, sixes=5),
        ],
        deliveries_found=1,
        processing_s=2.5,
        scorebox_found=True,
    )
    write_model(paths.summary_json, summary)
