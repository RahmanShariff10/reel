"""Tests for SoccerNet label loading, match preparation, and manifests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from eval.prepare import find_binary, prepare_match, probe_duration
from eval.soccernet import (
    KEY_ACTIONS,
    CameraLabel,
    Label,
    get_key_actions,
    key_actions,
    load_camera_labels,
    load_labels,
    load_manifest,
    to_match_time,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
V2_FIXTURE = FIXTURES_DIR / "sample_labels_v2.json"
CAMERAS_FIXTURE = FIXTURES_DIR / "sample_labels_cameras.json"


def test_labels_v2_loading_half_and_milliseconds() -> None:
    """Given a Labels-v2.json fixture, annotations load with right half and ms."""
    labels = load_labels(V2_FIXTURE)
    assert len(labels) == 8

    # First half annotations
    assert labels[0].half == 1
    assert labels[0].position_ms == 790722
    assert labels[0].label == "Goal"
    assert labels[0].team == "home"
    assert labels[0].visibility == "visible"
    assert labels[0].game_time == "1 - 13:10"

    assert labels[1].half == 1
    assert labels[1].position_ms == 1530000

    assert labels[2].half == 1
    assert labels[2].position_ms == 1980000

    assert labels[3].half == 1
    assert labels[3].position_ms == 2655000

    # Second half annotations
    assert labels[4].half == 2
    assert labels[4].position_ms == 600000
    assert labels[4].label == "Red card"
    assert labels[4].team == "home"

    assert labels[5].half == 2
    assert labels[5].position_ms == 1245000
    assert labels[5].label == "Yellow->red card"

    assert labels[6].half == 2
    assert labels[6].position_ms == 2100000
    assert labels[6].visibility == "unshown"

    assert labels[7].half == 2
    assert labels[7].position_ms == 2410000
    assert labels[7].label == "Substitution"


def test_to_match_time_second_half() -> None:
    """Given a 2nd-half label at 100 000 ms and first_half_s 2800, to_match_time returns 2900.0."""
    label = Label(
        half=2,
        game_time="2 - 01:40",
        position_ms=100000,
        label="Goal",
    )
    result = to_match_time(label, first_half_s=2800)
    assert result == 2900.0


def test_to_match_time_first_half() -> None:
    """First-half label match time is simply position in seconds."""
    label = Label(
        half=1,
        game_time="1 - 00:50",
        position_ms=50000,
        label="Goal",
    )
    result = to_match_time(label, first_half_s=2800)
    assert result == 50.0


def test_key_actions_filtering() -> None:
    """Given the fixture, only the five key-action labels are returned as key actions."""
    assert KEY_ACTIONS == {
        "Goal",
        "Penalty",
        "Red card",
        "Yellow->red card",
        "Shots on target",
    }

    labels = load_labels(V2_FIXTURE)
    filtered = key_actions(labels)
    assert len(filtered) == 5

    returned_names = {lbl.label for lbl in filtered}
    assert returned_names == KEY_ACTIONS

    # Check that get_key_actions returns the identical list
    assert get_key_actions(labels) == filtered

    # Check is_key_action property
    for lbl in labels:
        assert lbl.is_key_action == (lbl.label in KEY_ACTIONS)


def test_camera_labels_replay_flag() -> None:
    """Given a Labels-cameras.json-format fixture, replay is true only for 'replay' rows."""
    cameras = load_camera_labels(CAMERAS_FIXTURE)
    assert len(cameras) == 5

    for c in cameras:
        assert isinstance(c, CameraLabel)

    # Row 0: "replay": "real" -> False
    assert cameras[0].label == "Main camera center"
    assert cameras[0].replay is False

    # Row 1: "replay": "replay" -> True
    assert cameras[1].label == "Close-up player"
    assert cameras[1].replay is True

    # Row 2: "replay": "real" -> False
    assert cameras[2].replay is False

    # Row 3: "replay": "replay" -> True
    assert cameras[3].replay is True

    # Row 4: no replay field -> False
    assert cameras[4].replay is False

    # Also check load_labels on camera file
    labels_from_generic = load_labels(CAMERAS_FIXTURE)
    for orig, generic in zip(cameras, labels_from_generic, strict=True):
        assert getattr(generic, "replay", False) == orig.replay


def _create_synthetic_half_video(out_path: Path, duration_s: float, color: str) -> None:
    """Generate a short valid video stream with ffmpeg."""
    ffmpeg = find_binary("ffmpeg")
    cmd = [
        ffmpeg,
        "-y",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=320x240:r=25:d={duration_s}",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=r=44100:cl=mono:d={duration_s}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "aac",
        "-t",
        str(duration_s),
        str(out_path),
    ]
    subprocess.run(cmd, check=True)


def test_eval_prepare_stream_copy(tmp_path: Path) -> None:
    """Given 2 synthetic half videos, eval.prepare produces playable file with sum duration."""
    videos_dir = tmp_path / "videos"
    game_dir = videos_dir / "test_match"
    game_dir.mkdir(parents=True)

    half1 = game_dir / "1_720p.mkv"
    half2 = game_dir / "2_720p.mkv"
    _create_synthetic_half_video(half1, duration_s=2.0, color="blue")
    _create_synthetic_half_video(half2, duration_s=3.0, color="red")

    out_dir = tmp_path / "out"

    # Test via Python API
    meta = prepare_match(game="test_match", videos_dir=videos_dir, out_dir=out_dir)

    match_mkv = out_dir / "match.mkv"
    match_json = out_dir / "match.json"

    assert match_mkv.is_file()
    assert match_json.is_file()

    # Playable and sum duration ±0.5s
    duration = probe_duration(match_mkv)
    assert duration == pytest.approx(5.0, abs=0.5)
    assert meta["first_half_s"] == pytest.approx(2.0, abs=0.5)
    assert meta["duration_s"] == pytest.approx(5.0, abs=0.5)

    # Test via CLI invocation
    cli_out = tmp_path / "cli_out"
    repo_root = Path(__file__).parents[2]
    cmd = [
        sys.executable,
        "-m",
        "eval.prepare",
        "--game",
        "test_match",
        "--videos",
        str(videos_dir),
        "--out",
        str(cli_out),
    ]
    subprocess.run(cmd, check=True, cwd=repo_root)
    assert (cli_out / "match.mkv").is_file()
    assert (cli_out / "match.json").is_file()


def test_manifest_missing_required_fields(tmp_path: Path) -> None:
    """Given a manifest missing a required field, a clear error names the game and field."""
    # Missing 'split'
    manifest_missing_split = tmp_path / "missing_split.yaml"
    manifest_missing_split.write_text(
        """
matches:
  - game: chelsea_vs_burnley
    commentary_language: en
"""
    )
    with pytest.raises(ValueError) as excinfo:
        load_manifest(manifest_missing_split)
    msg = str(excinfo.value)
    assert "chelsea_vs_burnley" in msg
    assert "split" in msg

    # Missing 'commentary_language'
    manifest_missing_lang = tmp_path / "missing_lang.yaml"
    manifest_missing_lang.write_text(
        """
matches:
  - game: liverpool_vs_arsenal
    split: dev
"""
    )
    with pytest.raises(ValueError) as excinfo:
        load_manifest(manifest_missing_lang)
    msg = str(excinfo.value)
    assert "liverpool_vs_arsenal" in msg
    assert "commentary_language" in msg

    # Missing 'game'
    manifest_missing_game = tmp_path / "missing_game.yaml"
    manifest_missing_game.write_text(
        """
matches:
  - split: test
    commentary_language: en
"""
    )
    with pytest.raises(ValueError) as excinfo:
        load_manifest(manifest_missing_game)
    msg = str(excinfo.value)
    assert "game" in msg


def test_manifest_matches_yaml_structure() -> None:
    """Check that committed matches.yaml loads properly with 5 dev and 10 test games."""
    manifest_path = Path(__file__).parents[1] / "manifests" / "matches.yaml"
    assert manifest_path.is_file()

    entries = load_manifest(manifest_path)
    assert len(entries) == 15

    dev_entries = [e for e in entries if e.split == "dev"]
    test_entries = [e for e in entries if e.split == "test"]

    assert len(dev_entries) == 5
    assert len(test_entries) == 10

    for e in entries:
        assert e.game
        assert e.commentary_language == "en"
