"""Tests for slice-42-football-shots.

Acceptance criteria:
- With stub embeddings, zero-shot labels use the new classes.
- "Main camera center" maps to wide, "Close-up player or field referee" to close_up and
  "Public" to crowd.
- A replay row isn't used for training.
- With stub data, the classifier trains and writes shot_classifier.joblib.
"""

from __future__ import annotations

import json
import typing
from pathlib import Path

import numpy as np
import pytest

from reel.common.config import load_config
from reel.common.models import Shot, ShotLabel, write_model
from reel.common.paths import JobPaths
from reel.shots.classify import zero_shot
from reel.shots.label import CLASSES
from reel.shots.train import (
    CameraRow,
    labels_from_cameras,
    load_camera_rows,
    main,
    train,
    write_soccernet_labels,
)

CAMERA_MAP = load_config().shots.camera_map


class OrderedEmbedder:
    """The nth class's prompts embed to the nth axis, whatever they say."""

    def __init__(self, classes: int) -> None:
        self.classes, self.calls = classes, 0

    def embed_images(self, paths):
        raise AssertionError("images are not embedded in these tests")

    def embed_texts(self, texts):
        out = np.zeros((len(texts), self.classes), np.float32)
        out[:, self.calls] = 1.0
        self.calls += 1
        return out


class AxisEmbedder:
    def embed_images(self, paths):
        raise AssertionError("embeddings are cached in these tests")

    def embed_texts(self, texts):
        out = np.zeros((len(texts), len(CLASSES)), np.float32)
        for i, t in enumerate(texts):
            out[i, next(k for k, c in enumerate(CLASSES) if c in t)] = 1.0
        return out


def shot(i: int, start: float, end: float) -> Shot:
    return Shot(id=i, start_s=start, end_s=end, keyframe_path=f"keyframes/{i}.jpg")


class TestZeroShot:
    def test_default_prompts_cover_the_football_classes(self) -> None:
        assert set(load_config().shots.prompts) == set(typing.get_args(ShotLabel))

    def test_labels_use_the_new_classes(self) -> None:
        prompts = load_config().shots.prompts
        classes = list(prompts)
        labels, probs = zero_shot(
            np.eye(len(classes), dtype=np.float32), prompts, OrderedEmbedder(len(classes))
        )
        assert labels == classes
        for row in probs:
            assert set(row) == set(classes)

    def test_labelling_tool_uses_the_new_classes(self) -> None:
        assert set(CLASSES) == set(typing.get_args(ShotLabel))


class TestCameraMap:
    @pytest.mark.parametrize(
        ("camera", "label"),
        [
            ("Main camera center", "wide"),
            ("Close-up player or field referee", "close_up"),
            ("Public", "crowd"),
        ],
    )
    def test_required_mappings(self, camera: str, label: str) -> None:
        assert CAMERA_MAP[camera] == label

    def test_every_target_is_a_shot_label(self) -> None:
        assert set(CAMERA_MAP.values()) <= set(typing.get_args(ShotLabel))

    def test_map_is_config_driven(self) -> None:
        cfg = load_config(overrides={"shots": {"camera_map": {"Public": "wide"}}})
        assert cfg.shots.camera_map["Public"] == "wide"
        assert cfg.shots.camera_map["Main camera center"] == "wide"


class TestLabelsFromCameras:
    def test_uses_the_camera_at_the_keyframe(self) -> None:
        rows = [
            CameraRow(0.0, "Main camera center", False),
            CameraRow(10.0, "Public", False),
        ]
        shots = [shot(0, 0.0, 8.0), shot(1, 8.0, 20.0), shot(2, 12.0, 14.0)]
        assert labels_from_cameras(shots, rows, CAMERA_MAP) == {
            0: "wide",
            1: "crowd",
            2: "crowd",
        }

    def test_replay_row_not_used(self) -> None:
        rows = [
            CameraRow(0.0, "Main camera center", False),
            CameraRow(10.0, "Main camera center", True),
        ]
        assert labels_from_cameras([shot(0, 1.0, 3.0), shot(1, 11.0, 13.0)], rows, CAMERA_MAP) == {
            0: "wide"
        }

    def test_unmapped_camera_not_used(self) -> None:
        rows = [CameraRow(0.0, "I don't know", False)]
        assert labels_from_cameras([shot(0, 1.0, 3.0)], rows, CAMERA_MAP) == {}

    def test_shot_before_first_label_not_used(self) -> None:
        rows = [CameraRow(50.0, "Public", False)]
        assert labels_from_cameras([shot(0, 1.0, 3.0)], rows, CAMERA_MAP) == {}


def write_cameras(path: Path, rows: list[tuple[str, int, str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "annotations": [
                    {"gameTime": gt, "position": str(ms), "label": cam, "replay": replay}
                    for gt, ms, cam, replay in rows
                ]
            }
        )
    )


def test_second_half_rows_are_shifted(tmp_path: Path) -> None:
    path = tmp_path / "cams.json"
    write_cameras(
        path,
        [
            ("2 - 00:10", 10_000, "Public", "real-time"),
            ("1 - 00:05", 5_000, "Main camera left", "replay"),
        ],
    )
    assert load_camera_rows(path, 2800.0) == [
        CameraRow(5.0, "Main camera left", True),
        CameraRow(2810.0, "Public", False),
    ]


GAME = "league/season/2015-01-01 - Team A 1 - 0 Team B"


def make_soccernet_job(root: Path, per_class: int = 8) -> tuple[Path, np.ndarray]:
    """A job with shots and clustered embeddings, plus SoccerNet-format camera labels."""
    cameras = {
        "wide": "Main camera center",
        "medium": "Spider camera",
        "close_up": "Close-up corner",
        "crowd": "Public",
        "graphic": None,
    }
    trained = [c for c in CLASSES if cameras[c]]
    rng = np.random.default_rng(0)
    data_dir = root / "data"
    paths = JobPaths("job-1", data_dir=data_dir)
    paths.ensure_job_dir()

    shots, vectors, rows, t = [], [], [], 0.0
    for i in range(per_class * len(trained)):
        name = trained[i % len(trained)]
        shots.append(shot(i, t, t + 4.0))
        vectors.append(np.eye(len(CLASSES))[CLASSES.index(name)] + rng.normal(0, 0.2, len(CLASSES)))
        rows.append(("1 - 00:00", int(t * 1000), cameras[name], "real-time"))
        t += 4.0
    write_model(paths.shots_json, shots)
    embeddings = np.stack(vectors).astype(np.float32)
    np.save(paths.shot_embeddings_npy, embeddings)

    write_cameras(root / "labels" / GAME / "Labels-cameras.json", rows)
    prepared = root / "prepared" / GAME
    prepared.mkdir(parents=True)
    (prepared / "match.json").write_text(json.dumps({"first_half_s": 3000.0}))
    manifest = root / "manifest.yaml"
    manifest.write_text(
        "matches:\n"
        f"  - game: {GAME}\n    split: dev\n    commentary_language: en\n    job_id: job-1\n"
        "  - game: league/season/not processed yet\n    split: dev\n    commentary_language: en\n"
    )
    return manifest, embeddings


class TestTrainingFromSoccerNet:
    def test_writes_labels_without_images(self, tmp_path: Path) -> None:
        manifest, _ = make_soccernet_job(tmp_path)
        count = write_soccernet_labels(
            manifest,
            tmp_path / "labels",
            tmp_path / "prepared",
            tmp_path / "data",
            tmp_path / "csv",
            CAMERA_MAP,
        )
        files = list((tmp_path / "csv").iterdir())
        assert count == 32 and len(files) == 1
        assert files[0].read_text().splitlines()[0] == "job_id,match_id,shot_id,label"

    def test_classifier_trains_and_writes_model(self, tmp_path: Path) -> None:
        manifest, _ = make_soccernet_job(tmp_path)
        write_soccernet_labels(
            manifest,
            tmp_path / "labels",
            tmp_path / "prepared",
            tmp_path / "data",
            tmp_path / "csv",
            CAMERA_MAP,
        )
        model = tmp_path / "models" / "shot_classifier.joblib"

        result = train(
            tmp_path / "csv",
            tmp_path / "data",
            model,
            tmp_path / "report.md",
            embedder=AxisEmbedder(),
            prompts={c: [f"a photo of {c}"] for c in CLASSES},
        )

        assert model.is_file()
        assert result["classifier"]["accuracy"] > 0.9
        assert "### Zero-shot CLIP (baseline)" in (tmp_path / "report.md").read_text()

    def test_no_processed_jobs_is_an_error(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(
            "matches:\n  - game: a/b/c\n    split: dev\n    commentary_language: en\n"
        )
        with pytest.raises(ValueError, match="job_id"):
            write_soccernet_labels(
                manifest,
                tmp_path,
                tmp_path,
                tmp_path,
                tmp_path / "csv",
                CAMERA_MAP,
            )

    def test_cli_option_exists(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main(["--help"])
        assert "--from-soccernet" in capsys.readouterr().out
