"""Shared pytest fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures.make_synthetic import generate_synthetic_video


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
