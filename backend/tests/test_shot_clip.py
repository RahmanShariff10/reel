"""Tests for slice-14-shot-clip-zeroshot.

Acceptance criteria:
- With a stub embedder, every shot gets a label and probabilities summing to 1 (±0.001).
- With a valid cached shot_embeddings.npy, a re-run does not call the embedder.
- With the model already downloaded, the stage works with no network.
- Changed prompts in config change labels with no code change.
"""

from __future__ import annotations

import socket
from pathlib import Path

import numpy as np
import pytest

from reel.common.config import load_config
from reel.common.models import Shot, read_model, write_model
from reel.common.paths import JobPaths
from reel.jobs.pipeline import PipelineContext
from reel.shots.classify import ClipEmbedder, is_valid_classify_shots, run_classify_shots

REPO_MODELS = Path(__file__).resolve().parents[2] / "data" / "models"
CLASSES = ["run_up", "close_up", "crowd", "field", "graphic"]


class StubEmbedder:
    """Images embed by file name; each text embeds to the axis of the class it names."""

    def __init__(self) -> None:
        self.image_calls = 0

    def embed_images(self, paths):
        self.image_calls += 1
        out = np.zeros((len(paths), len(CLASSES)), np.float32)
        for i, p in enumerate(paths):
            out[i, i % len(CLASSES)] = 1.0
        return out

    def embed_texts(self, texts):
        out = np.zeros((len(texts), len(CLASSES)), np.float32)
        for i, t in enumerate(texts):
            out[i, next(k for k, c in enumerate(CLASSES) if c in t)] = 1.0
        return out


def make_job(tmp: Path, n_shots: int = 7, overrides: dict | None = None) -> PipelineContext:
    paths = JobPaths("job", data_dir=tmp)
    paths.keyframes_dir.mkdir(parents=True)
    shots = []
    for i in range(n_shots):
        (paths.keyframes_dir / f"shot_{i:05d}.jpg").write_bytes(b"jpg")
        shots.append(
            Shot(id=i, start_s=i, end_s=i + 1, keyframe_path=f"keyframes/shot_{i:05d}.jpg")
        )
    write_model(paths.shots_json, shots)
    prompts = {c: [f"a photo of {c}"] for c in CLASSES}
    cfg = load_config(overrides={"shots": {"prompts": prompts}, **(overrides or {})})
    return PipelineContext(job_id="job", db_path=tmp / "db", paths=paths, config=cfg)


class TestStub:
    def test_labels_and_probabilities(self, tmp_path: Path) -> None:
        ctx = make_job(tmp_path)
        run_classify_shots(ctx, embedder=StubEmbedder())
        shots = read_model(ctx.paths.shots_json, list[Shot])
        assert [s.label for s in shots] == [CLASSES[i % 5] for i in range(7)]
        for s in shots:
            assert abs(sum(s.probabilities.values()) - 1.0) <= 0.001
            assert s.label_source == "zero_shot"
        assert is_valid_classify_shots(ctx)

    def test_cached_embeddings_reused(self, tmp_path: Path) -> None:
        ctx = make_job(tmp_path)
        first = StubEmbedder()
        run_classify_shots(ctx, embedder=first)
        assert first.image_calls == 1
        second = StubEmbedder()
        run_classify_shots(ctx, embedder=second)
        assert second.image_calls == 0

    def test_prompts_from_config_change_labels(self, tmp_path: Path) -> None:
        # Swap the run_up and crowd prompts: shots embedded on the run_up axis become crowd.
        swapped = {c: [f"a photo of {c}"] for c in CLASSES}
        swapped["run_up"], swapped["crowd"] = ["a photo of crowd"], ["a photo of run_up"]
        ctx = make_job(tmp_path, overrides={"shots": {"prompts": swapped}})
        run_classify_shots(ctx, embedder=StubEmbedder())
        shots = read_model(ctx.paths.shots_json, list[Shot])
        assert shots[0].label == "crowd" and shots[2].label == "run_up"


@pytest.mark.skipif(
    not REPO_MODELS.is_dir() or not any(REPO_MODELS.iterdir()),
    reason="CLIP weights not downloaded to data/models",
)
class TestRealClipOffline:
    def test_runs_without_network(self, scanned_match: PipelineContext, monkeypatch) -> None:
        def no_network(*args, **kwargs):
            raise OSError("network disabled in test")

        monkeypatch.setattr(socket.socket, "connect", no_network)
        cfg = scanned_match.config.model_copy(update={"models_dir": REPO_MODELS})
        embedder = ClipEmbedder(cfg.shots, REPO_MODELS)
        ctx = PipelineContext(
            job_id="job", db_path=scanned_match.db_path, paths=scanned_match.paths, config=cfg
        )
        run_classify_shots(ctx, embedder=embedder)
        shots = read_model(ctx.paths.shots_json, list[Shot])
        assert shots and all(s.label in CLASSES for s in shots)
        emb = np.load(ctx.paths.shot_embeddings_npy)
        assert emb.shape == (len(shots), 512)
