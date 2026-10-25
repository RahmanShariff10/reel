"""Tests for slice-16-audio-excitement.

Acceptance criteria:
- Synthetic video with PANNs off: excitement has a local maximum within ±1 s of every
  scheduled burst, and the median excitement outside bursts is < 0.3.
- PANNs class indices are resolved by name (a test fails if a name is missing).
- A video of duration d gives ceil(d) rows.
- has_audio: false → all values 0 and the stage succeeds.
- With a stub PANNs model, the combined excitement follows the configured weights.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from reel.audio.excitement import (
    COLUMNS,
    CROWD_CLASSES,
    PannsTagger,
    compute_excitement,
    is_valid_audio,
    resolve_indices,
    run_audio,
)
from reel.common.config import AudioConfig, load_config
from reel.common.models import Meta, read_excitement_csv, write_model
from reel.common.paths import JobPaths
from reel.jobs.pipeline import PipelineContext
from tests.conftest import SyntheticMatch

REPO_MODELS = Path(__file__).resolve().parents[2] / "data" / "models"


class StubTagger:
    labels = ["Speech", "Cheering", "Music", "Applause", "Crowd"]

    def tag(self, windows: np.ndarray) -> np.ndarray:
        out = np.zeros((len(windows), len(self.labels)))
        out[:, [1, 3, 4]] = 0.1  # cheer + applause + crowd = 0.3
        return out


def rows_of(path: Path) -> list[dict[str, str]]:
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


class TestSyntheticLoudness:
    def test_peaks_at_bursts(self, scanned_match: PipelineContext, synthetic_match) -> None:
        cfg = scanned_match.config.model_copy(deep=True)
        cfg.audio.use_panns = False
        ctx = PipelineContext(
            job_id="job", db_path=scanned_match.db_path, paths=scanned_match.paths, config=cfg
        )
        run_audio(ctx)
        assert is_valid_audio(ctx)
        exc = np.array(read_excitement_csv(ctx.paths.excitement_csv))
        bursts = synthetic_match.schedule["bursts"]
        inside = np.zeros(len(exc), bool)
        for b0, b1 in bursts:
            lo, hi = max(0, math.floor(b0) - 1), min(len(exc), math.ceil(b1) + 2)
            inside[lo:hi] = True
            peak = lo + int(np.argmax(exc[lo:hi]))
            assert b0 - 1 <= peak <= b1 + 1
            assert exc[peak] > exc[max(0, lo - 4) : lo].max(initial=0) + 0.3
        assert np.median(exc[~inside]) < 0.3
        assert rows_of(ctx.paths.excitement_csv)[0].keys() == set(COLUMNS)


class TestRules:
    def test_indices_by_name(self) -> None:
        assert resolve_indices(StubTagger.labels) == [1, 3, 4]
        with pytest.raises(KeyError, match="Applause"):
            resolve_indices(["Speech", "Cheering", "Crowd"])

    def test_row_count_ceil_duration(self) -> None:
        assert len(compute_excitement(None, 10.3, AudioConfig())) == 11
        assert len(compute_excitement(None, 120.0, AudioConfig())) == 120

    def test_stub_tagger_follows_weights(self, scanned_match: PipelineContext) -> None:
        wav = scanned_match.paths.audio_wav
        crowd_only = AudioConfig(weight_loudness=0.0, weight_crowd=1.0, crowd_prob_full=0.6)
        rows = compute_excitement(wav, 20.0, crowd_only, StubTagger())
        assert all(r["excitement"] == pytest.approx(0.5) for r in rows)  # 0.3 / 0.6
        both = AudioConfig(weight_loudness=1.0, weight_crowd=1.0, crowd_prob_full=0.6)
        rows = compute_excitement(wav, 20.0, both, StubTagger())
        quiet = [r for r in rows if r["loudness_z"] <= 0]
        assert quiet and all(r["excitement"] == pytest.approx(0.25) for r in quiet)

    def test_no_audio_all_zero(self, tmp_path: Path) -> None:
        paths = JobPaths("job", data_dir=tmp_path)
        write_model(
            paths.meta_json,
            Meta(duration_s=12.5, width=1280, height=720, fps=25.0, has_audio=False),
        )
        ctx = PipelineContext(
            job_id="job", db_path=tmp_path / "db", paths=paths, config=load_config()
        )
        run_audio(ctx)
        rows = rows_of(paths.excitement_csv)
        assert len(rows) == 13
        assert all(float(r[c]) == 0.0 for r in rows for c in COLUMNS if c != "second")
        assert is_valid_audio(ctx)


@pytest.mark.skipif(
    not (REPO_MODELS / "Cnn14_mAP=0.431.pth").is_file(),
    reason="PANNs checkpoint not downloaded to data/models",
)
class TestRealPanns:
    def test_real_labels_and_probabilities(
        self, synthetic_match: SyntheticMatch, scanned_match: PipelineContext
    ) -> None:
        tagger = PannsTagger(REPO_MODELS)
        assert len(resolve_indices(tagger.labels, CROWD_CLASSES)) == 3
        rows = compute_excitement(scanned_match.paths.audio_wav, 10.0, AudioConfig(), tagger)
        assert all(0.0 <= r["p_cheer"] <= 1.0 and 0.0 <= r["excitement"] <= 1.0 for r in rows)
