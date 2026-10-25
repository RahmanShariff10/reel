"""Tests for slice-15-shot-classifier.

Acceptance criteria:
- Labelling tool: keys 1-5 / s / u / q behave as described; reopening resumes at the
  first unlabelled shot.
- With >= 500 labels, training writes the model file and the report (classifier vs
  zero-shot).
- Same labels and seed → identical predictions.
- With the model file present, shots.json uses label_source "classifier"; without it,
  "zero_shot".
"""

from __future__ import annotations

import csv
from pathlib import Path

import joblib
import numpy as np

from reel.common.config import load_config
from reel.common.models import Shot, read_model, write_model
from reel.common.paths import JobPaths
from reel.jobs.pipeline import PipelineContext
from reel.shots.classify import run_classify_shots
from reel.shots.label import CLASSES, LabelSession
from reel.shots.train import train

DIM = len(CLASSES)


class AxisEmbedder:
    """Texts naming a class embed onto that class's axis (matches the synthetic data)."""

    def embed_images(self, paths):
        raise AssertionError("embeddings are cached in these tests")

    def embed_texts(self, texts):
        out = np.zeros((len(texts), DIM), np.float32)
        for i, t in enumerate(texts):
            out[i, next(k for k, c in enumerate(CLASSES) if c in t)] = 1.0
        return out


PROMPTS = {c: [f"a photo of {c}"] for c in CLASSES}


def make_labelled_jobs(data_dir: Path, labels_dir: Path, per_job: int = 260) -> None:
    """Two matches of clustered synthetic embeddings plus their label CSVs."""
    rng = np.random.default_rng(0)
    for m in range(2):
        job, match = f"job{m}", f"match{m}"
        y = [CLASSES[i % DIM] for i in range(per_job)]
        X = np.stack([np.eye(DIM)[CLASSES.index(c)] for c in y]) + rng.normal(
            0, 0.35, (per_job, DIM)
        )
        paths = JobPaths(job, data_dir=data_dir)
        paths.ensure_job_dir()
        np.save(paths.shot_embeddings_npy, X.astype(np.float32))
        labels_dir.mkdir(parents=True, exist_ok=True)
        with open(labels_dir / f"shots_{match}.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["job_id", "match_id", "shot_id", "label"])
            w.writerows([job, match, i, c] for i, c in enumerate(y))


class TestLabelSession:
    def test_keys(self, tmp_path: Path) -> None:
        out = tmp_path / "shots_m.csv"
        s = LabelSession("job", "m", [0, 1, 2, 3], out)
        assert s.current == 0
        assert s.key("1") and s.labels[0] == "run_up"
        assert s.key("s") and s.labels[1] == "skip"
        assert s.key("x") and s.current == 2  # unknown key does nothing
        assert s.key("u") and 1 not in s.labels and s.current == 1
        assert s.key("5") and s.labels[1] == "graphic"
        assert s.key("q") is False
        rows = list(csv.DictReader(open(out)))
        assert [(r["shot_id"], r["label"]) for r in rows] == [("0", "run_up"), ("1", "graphic")]

    def test_resume_at_first_unlabelled(self, tmp_path: Path) -> None:
        out = tmp_path / "shots_m.csv"
        first = LabelSession("job", "m", [0, 1, 2], out)
        first.key("2")
        first.key("s")
        again = LabelSession("job", "m", [0, 1, 2], out)
        assert again.current == 2
        assert again.key("3") is False  # last shot labelled → done
        assert again.current is None


class TestTraining:
    def test_trains_model_and_report(self, tmp_path: Path) -> None:
        make_labelled_jobs(tmp_path / "data", tmp_path / "labels")
        model, report = tmp_path / "models" / "clf.joblib", tmp_path / "report.md"
        result = train(
            tmp_path / "labels",
            tmp_path / "data",
            model,
            report,
            embedder=AxisEmbedder(),
            prompts=PROMPTS,
        )
        assert model.is_file()
        text = report.read_text()
        assert "520 labelled shots from 2 match(es); validation: leave-one-match-out" in text
        assert "### Trained classifier" in text and "### Zero-shot CLIP (baseline)" in text
        assert result["classifier"]["accuracy"] > 0.9

    def test_deterministic(self, tmp_path: Path) -> None:
        make_labelled_jobs(tmp_path / "data", tmp_path / "labels")
        X = np.random.default_rng(1).normal(0, 1, (50, DIM))
        preds = []
        for run in range(2):
            out = tmp_path / f"m{run}.joblib"
            train(
                tmp_path / "labels",
                tmp_path / "data",
                out,
                tmp_path / "r.md",
                embedder=AxisEmbedder(),
                prompts=PROMPTS,
            )
            preds.append(joblib.load(out).predict(X))
        assert (preds[0] == preds[1]).all()


class TestPipelineUsesClassifier:
    def _job(self, tmp: Path, models_dir: Path) -> PipelineContext:
        paths = JobPaths("job", data_dir=tmp / "data")
        paths.keyframes_dir.mkdir(parents=True)
        shots = [
            Shot(id=i, start_s=i, end_s=i + 1, keyframe_path=f"keyframes/{i}.jpg")
            for i in range(DIM)
        ]
        write_model(paths.shots_json, shots)
        np.save(paths.shot_embeddings_npy, np.eye(DIM, dtype=np.float32))
        # REEL_MODELS_DIR (set for the test suite) outranks overrides, so set it directly.
        cfg = load_config(overrides={"shots": {"prompts": PROMPTS}})
        cfg = cfg.model_copy(update={"models_dir": models_dir})
        return PipelineContext(job_id="job", db_path=tmp / "db", paths=paths, config=cfg)

    def test_label_source(self, tmp_path: Path) -> None:
        models = tmp_path / "models"
        ctx = self._job(tmp_path, models)
        run_classify_shots(ctx, embedder=AxisEmbedder())
        assert {s.label_source for s in read_model(ctx.paths.shots_json, list[Shot])} == {
            "zero_shot"
        }

        make_labelled_jobs(tmp_path / "train_data", tmp_path / "labels")
        train(
            tmp_path / "labels",
            tmp_path / "train_data",
            models / "shot_classifier.joblib",
            tmp_path / "r.md",
            embedder=AxisEmbedder(),
            prompts=PROMPTS,
        )
        run_classify_shots(ctx, embedder=AxisEmbedder())
        shots = read_model(ctx.paths.shots_json, list[Shot])
        assert {s.label_source for s in shots} == {"classifier"}
        assert [s.label for s in shots] == CLASSES
