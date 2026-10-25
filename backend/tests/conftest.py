"""Shared pytest fixtures."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures.make_synthetic import generate_synthetic_video

# Reuse the developer's downloaded model weights (repo-root data/models) in tests,
# so pipeline tests never download models into backend/data.
os.environ.setdefault(
    "REEL_MODELS_DIR", str(Path(__file__).resolve().parents[2] / "data" / "models")
)


@dataclass(frozen=True)
class SyntheticMatch:
    """A generated synthetic match: video file plus its ground-truth schedule."""

    video: Path
    schedule_path: Path
    schedule: dict[str, Any]


def make_synthetic_match(out_dir: Path, **kwargs: Any) -> SyntheticMatch:
    video, schedule_path = generate_synthetic_video(out_dir, **kwargs)
    return SyntheticMatch(video, schedule_path, json.loads(schedule_path.read_text()))


@pytest.fixture(scope="session")
def synthetic_match(tmp_path_factory: pytest.TempPathFactory) -> SyntheticMatch:
    """Default 120 s synthetic match (score box, audio, no distractor), built once."""
    return make_synthetic_match(tmp_path_factory.mktemp("synthetic_match"))


@pytest.fixture(scope="session")
def scanned_match(synthetic_match: SyntheticMatch, tmp_path_factory: pytest.TempPathFactory):
    """The default synthetic match run through ingest, locate_scorebox and scan, once.

    Returns the PipelineContext; ``ctx.progress_calls`` holds the scan's progress updates.
    """
    from reel.common.config import load_config
    from reel.common.paths import JobPaths
    from reel.ingest.scan import run_scan
    from reel.ingest.stage import run_ingest
    from reel.jobs.pipeline import PipelineContext
    from reel.scoreboard.stage import run_locate_scorebox

    tmp = tmp_path_factory.mktemp("scanned_match")
    paths = JobPaths("job", data_dir=tmp)
    paths.ensure_job_dir()
    ctx = PipelineContext(job_id="job", db_path=tmp / "reel.db", paths=paths,
                          config=load_config(), input_path=synthetic_match.video)
    run_ingest(ctx)
    run_locate_scorebox(ctx)
    calls: list[float] = []
    run_scan(ctx, calls.append)
    ctx.progress_calls = calls  # type: ignore[attr-defined]
    return ctx
