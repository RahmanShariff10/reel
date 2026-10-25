"""Tests for slice-02-common-models: JobPaths resolution against ARCHITECTURE.md.

Acceptance criterion:
- Given ARCHITECTURE.md's job directory list, when checking JobPaths,
  then every listed file and folder has a property with exactly that name.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from reel.common.paths import JobPaths


@pytest.fixture
def paths(tmp_path: Path) -> JobPaths:
    return JobPaths("test-job-123", data_dir=tmp_path)


class TestJobPathsArchitectureList:
    """Verify all files and directories specified in ARCHITECTURE.md exist as properties."""

    def test_root_directory(self, paths: JobPaths, tmp_path: Path):
        expected = tmp_path / "jobs" / "test-job-123"
        assert paths.root == expected

    def test_stage_1_ingest_paths(self, paths: JobPaths):
        assert paths.meta_json.name == "meta.json"
        assert paths.meta.name == "meta.json"
        assert paths.audio_wav.name == "audio.wav"
        assert paths.audio.name == "audio.wav"
        assert paths.input_file.name == "input.mp4"
        assert paths.input_path("mkv").name == "input.mkv"

    def test_stage_2_scorebox_paths(self, paths: JobPaths):
        assert paths.scorebox_json.name == "scorebox.json"
        assert paths.scorebox.name == "scorebox.json"
        assert paths.scorebox_preview_jpg.name == "scorebox_preview.jpg"
        assert paths.scorebox_preview.name == "scorebox_preview.jpg"

    def test_stage_3_scan_paths(self, paths: JobPaths):
        assert paths.shots_json.name == "shots.json"
        assert paths.shots.name == "shots.json"
        assert paths.keyframes_dir.name == "keyframes"
        assert paths.keyframes.name == "keyframes"
        assert paths.score_crops_dir.name == "score_crops"
        assert paths.score_crops.name == "score_crops"

    def test_stage_4_read_score_paths(self, paths: JobPaths):
        assert paths.score_readings_json.name == "score_readings.json"
        assert paths.score_readings.name == "score_readings.json"
        assert paths.score_timeline_json.name == "score_timeline.json"
        assert paths.score_timeline.name == "score_timeline.json"
        assert paths.score_events_json.name == "score_events.json"
        assert paths.score_events.name == "score_events.json"

    def test_stage_5_classify_shots_paths(self, paths: JobPaths):
        assert paths.shot_embeddings_npy.name == "shot_embeddings.npy"
        assert paths.shot_embeddings.name == "shot_embeddings.npy"

    def test_stage_6_audio_paths(self, paths: JobPaths):
        assert paths.excitement_csv.name == "excitement.csv"
        assert paths.excitement.name == "excitement.csv"

    def test_stage_7_deliveries_paths(self, paths: JobPaths):
        assert paths.deliveries_json.name == "deliveries.json"
        assert paths.deliveries.name == "deliveries.json"

    def test_stage_8_highlights_paths(self, paths: JobPaths):
        assert paths.events_json.name == "events.json"
        assert paths.events.name == "events.json"
        assert paths.reel_plan.name == "reel_plan_5min.json"
        assert paths.reel_plan_path("3min").name == "reel_plan_3min.json"
        assert paths.reel_plan_json("10min").name == "reel_plan_10min.json"

    def test_stage_9_render_paths(self, paths: JobPaths):
        assert paths.clips_dir.name == "clips"
        assert paths.clips.name == "clips"
        assert paths.reel.name == "reel_5min.mp4"
        assert paths.reel_path("all").name == "reel_all.mp4"
        assert paths.title_png.name == "title.png"
        assert paths.title.name == "title.png"
        assert paths.summary_json.name == "summary.json"
        assert paths.summary.name == "summary.json"

    def test_all_architecture_items_accessible(self, paths: JobPaths):
        """ARCHITECTURE.md job directory items:
        meta.json, audio.wav, scorebox.json, scorebox_preview.jpg, shots.json,
        keyframes, score_crops, score_readings.json, score_timeline.json,
        score_events.json, shot_embeddings.npy, excitement.csv, deliveries.json,
        events.json, reel_plan_<mode>.json, clips, reel_<mode>.mp4, title.png, summary.json
        """
        arch_items = [
            "meta.json",
            "audio.wav",
            "scorebox.json",
            "scorebox_preview.jpg",
            "shots.json",
            "keyframes",
            "score_crops",
            "score_readings.json",
            "score_timeline.json",
            "score_events.json",
            "shot_embeddings.npy",
            "excitement.csv",
            "deliveries.json",
            "events.json",
            "clips",
            "title.png",
            "summary.json",
        ]
        for item in arch_items:
            path_val = paths[item]
            assert isinstance(path_val, Path)
            assert path_val.name == item.rstrip("/")

    def test_ensure_job_dir(self, paths: JobPaths):
        assert not paths.root.exists()
        created = paths.ensure_job_dir()
        assert created.is_dir()
        assert paths.root.exists()
