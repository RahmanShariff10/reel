"""Tests for slice-02-common-models and slice-36-football-models.

Acceptance criteria:
- Any model instance, when written with write_model and read back with read_model,
  equals original.
- When write raises mid-way, no partial file exists at target path.
- When file has invalid content, is_valid returns false (no exception).
- Event serialized to JSON keys match ARCHITECTURE.md Event shape (including types).
- excitement.csv helpers round-trip values with one row per second.
- Football: home -1 fails; Moment.minute accepts "45+2" or null; Event type "wicket" fails.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from reel.common.models import (
    ClipBoundary,
    Event,
    EventType,
    ExcitementEntry,
    HalfSummary,
    Meta,
    Moment,
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
    read_excitement_csv,
    read_excitement_entries,
    read_model,
    write_excitement_csv,
    write_model,
)


class TestModelRoundTrip:
    """AC: Given any model instance, write_model + read_model equals original."""

    def test_meta_roundtrip(self, tmp_path: Path):
        meta = Meta(
            duration_s=12400.5,
            width=1920,
            height=1080,
            fps=29.97,
            video_codec="h264",
            audio_codec="aac",
            audio_sample_rate=32000,
            audio_channels=1,
            size_bytes=4200000000,
        )
        p = write_model(tmp_path / "meta.json", meta)
        loaded = read_model(p, Meta)
        assert loaded == meta

    def test_scorebox_roundtrip(self, tmp_path: Path):
        scorebox = Scorebox(
            found=True,
            box=[50, 30, 420, 54],
            clock_box=[390, 30, 80, 54],
            confidence=0.96,
            sample_reading="ARS 1-0 CHE 34:12",
            sample_time_s=2040.5,
            preview_url="/api/files/test-job/scorebox_preview.jpg",
        )
        p = write_model(tmp_path / "scorebox.json", scorebox)
        loaded = read_model(p, Scorebox)
        assert loaded == scorebox

    def test_scorebox_not_found_roundtrip(self, tmp_path: Path):
        scorebox = Scorebox(found=False, confidence=0.1)
        p = write_model(tmp_path / "scorebox.json", scorebox)
        loaded = read_model(p, Scorebox)
        assert loaded == scorebox
        assert loaded.box is None

    def test_shot_roundtrip(self, tmp_path: Path):
        shot = Shot(
            id=42,
            start_s=120.0,
            end_s=125.5,
            duration_s=5.5,
            keyframe_path="keyframes/shot_0042.jpg",
            label="wide",
            probabilities={"wide": 0.88, "close_up": 0.05, "crowd": 0.02, "medium": 0.05},
        )
        p = write_model(tmp_path / "shot.json", shot)
        loaded = read_model(p, Shot)
        assert loaded == shot

    def test_shots_list_roundtrip(self, tmp_path: Path):
        shots = [
            Shot(id=0, start_s=0.0, end_s=3.0, label="graphic"),
            Shot(id=1, start_s=3.0, end_s=8.5, label="wide"),
        ]
        p = write_model(tmp_path / "shots.json", shots)
        loaded = read_model(p, list[Shot])
        assert loaded == shots

    def test_score_reading_roundtrip(self, tmp_path: Path):
        reading = ScoreReading(
            time_s=145.0,
            raw_text="ARS 1-0 CHE 34:12",
            home_code="ARS",
            away_code="CHE",
            home=1,
            away=0,
            clock_s=2052,
            confidence=0.92,
            visible=True,
        )
        p = write_model(tmp_path / "reading.json", reading)
        loaded = read_model(p, ScoreReading)
        assert loaded == reading

    def test_score_timeline_entry_roundtrip(self, tmp_path: Path):
        entry = ScoreTimelineEntry(
            time_s=145.0, home=1, away=0, visible=True, half=1, clock_s=2052, in_play=True
        )
        p = write_model(tmp_path / "timeline.json", entry)
        loaded = read_model(p, ScoreTimelineEntry)
        assert loaded == entry

    def test_score_event_roundtrip(self, tmp_path: Path):
        event = ScoreEvent(
            type="goal", time_s=146.0, side="home", home=1, away=0, half=1, clock_s=2052
        )
        p = write_model(tmp_path / "score_event.json", event)
        loaded = read_model(p, ScoreEvent)
        assert loaded == event

    def test_moment_roundtrip(self, tmp_path: Path):
        moment = Moment(
            id="m-012",
            half=2,
            minute="67",
            t_moment_s=4020.5,
            play_start_s=4005.0,
            sources=["goal", "audio", "replay"],
            goal=True,
            side="home",
            score_after="ARS 2-1 CHE",
            replay_count=2,
            excitement_max=0.88,
        )
        p = write_model(tmp_path / "moment.json", moment)
        loaded = read_model(p, Moment)
        assert loaded == moment

    def test_event_roundtrip(self, tmp_path: Path):
        event = Event(
            id="ev-01",
            moment_id="m-012",
            type="goal",
            half=2,
            minute="67",
            score_text="ARS 2-1 CHE",
            importance=0.92,
            confidence=0.95,
            reasons=[
                Reason(signal="score", value=1, label="score +1"),
                Reason(signal="audio", value=0.88, label="crowd excitement high"),
                Reason(signal="replays", value=2, label="2 replays"),
            ],
            moment_s=4020.5,
            clip=ClipBoundary(start_s=4000.5, end_s=4045.5),
        )
        p = write_model(tmp_path / "event.json", event)
        loaded = read_model(p, Event)
        assert loaded == event

    def test_reel_plan_roundtrip(self, tmp_path: Path):
        plan = ReelPlan(
            mode="5min",
            duration_s=298.5,
            clips=[
                ReelClip(
                    event_id="ev-01",
                    start_s=138.5,
                    end_s=156.5,
                    duration_s=18.0,
                    caption="GOAL · 67' · ARS 2-1 CHE",
                    offset_s=3.0,
                ),
            ],
        )
        p = write_model(tmp_path / "reel_plan.json", plan)
        loaded = read_model(p, ReelPlan)
        assert loaded == plan

    def test_summary_roundtrip(self, tmp_path: Path):
        summary = Summary(
            teams=["ARS", "CHE"],
            final_score="ARS 2-1 CHE",
            halves=[
                HalfSummary(home_goals=1, away_goals=0),
                HalfSummary(home_goals=1, away_goals=1),
            ],
            moments_found=41,
            processing_s=1820.4,
            scorebox_found=True,
        )
        p = write_model(tmp_path / "summary.json", summary)
        loaded = read_model(p, Summary)
        assert loaded == summary


class TestFootballValidation:
    """Slice 36: football-specific validation."""

    def test_negative_home_goals_rejected(self):
        with pytest.raises(ValidationError):
            ScoreReading(time_s=1.0, home=-1)

    @pytest.mark.parametrize("minute", ["45+2", None])
    def test_moment_minute(self, minute: str | None):
        assert Moment(id="m", t_moment_s=1.0, play_start_s=0.0, minute=minute).minute == minute

    def test_cricket_event_type_rejected(self):
        with pytest.raises(ValidationError):
            Event(
                id="ev",
                type="wicket",
                importance=0.5,
                confidence=0.5,
                moment_s=1.0,
                clip=ClipBoundary(start_s=0.0, end_s=2.0),
            )

    def test_cricket_shot_label_rejected(self):
        with pytest.raises(ValidationError):
            Shot(id=0, start_s=0.0, end_s=1.0, label="run_up")

    def test_cricket_names_stay_importable_until_slice_49(self):
        """Build order fix A: reel.jobs imports the cricket modules at load time."""
        import importlib

        from reel.common.models import Delivery, InningsSummary

        assert importlib.import_module("reel.jobs") is not None
        assert Delivery and InningsSummary


class TestAtomicWriteFailure:
    """AC: When a write raises mid-way, no partial file exists at target path."""

    def test_no_partial_file_on_serialization_failure(self, tmp_path: Path, monkeypatch):
        target = tmp_path / "important.json"

        # Monkeypatch json dumping or TypeAdapter to simulate mid-write failure
        from pydantic import TypeAdapter

        def bad_dump_json(self, *args, **kwargs):
            raise RuntimeError("Disk error simulated mid-serialization")

        monkeypatch.setattr(TypeAdapter, "dump_json", bad_dump_json)

        meta = Meta(duration_s=10.0, width=1280, height=720, fps=30.0)
        with pytest.raises(RuntimeError):
            write_model(target, meta)

        assert not target.exists()
        # Ensure no leftover temp files
        temp_files = list(tmp_path.glob(".*.tmp"))
        assert len(temp_files) == 0

    def test_existing_target_not_corrupted_on_write_failure(self, tmp_path: Path, monkeypatch):
        target = tmp_path / "existing.json"
        original = Meta(duration_s=50.0, width=1920, height=1080, fps=25.0)
        write_model(target, original)
        assert target.exists()

        from pydantic import TypeAdapter

        def bad_dump_json(self, *args, **kwargs):
            raise RuntimeError("Disk write failure")

        monkeypatch.setattr(TypeAdapter, "dump_json", bad_dump_json)

        new_meta = Meta(duration_s=999.0, width=640, height=360, fps=15.0)
        with pytest.raises(RuntimeError):
            write_model(target, new_meta)

        # Target should retain original content uncorrupted
        loaded = read_model(target, Meta)
        assert loaded == original


class TestValidationCheck:
    """AC: Given a file with invalid content, is_valid returns false without raising."""

    def test_valid_file_returns_true(self, tmp_path: Path):
        meta = Meta(duration_s=10.0, width=1280, height=720, fps=30.0)
        p = write_model(tmp_path / "meta.json", meta)
        assert is_valid(p, Meta) is True

    def test_missing_file_returns_false(self, tmp_path: Path):
        assert is_valid(tmp_path / "nonexistent.json", Meta) is False

    def test_corrupt_json_returns_false(self, tmp_path: Path):
        p = tmp_path / "corrupt.json"
        p.write_text("{ incomplete json ...")
        assert is_valid(p, Meta) is False

    def test_schema_mismatch_returns_false(self, tmp_path: Path):
        p = tmp_path / "wrong.json"
        # duration_s must be non-negative, width must be > 0
        p.write_text(json.dumps({"duration_s": -50, "width": -10, "height": 720, "fps": 30.0}))
        assert is_valid(p, Meta) is False


class TestEventSerializationShape:
    """AC: Event JSON keys match the Event shape in ARCHITECTURE.md."""

    @pytest.mark.parametrize(
        "event_type", ["goal", "penalty", "red_card", "chance", "yellow_card", "moment"]
    )
    def test_event_types_supported(self, event_type: EventType):
        event = Event(
            id=f"ev-{event_type}",
            type=event_type,
            importance=0.8,
            confidence=0.9,
            moment_s=100.0,
            clip=ClipBoundary(start_s=95.0, end_s=115.0),
        )
        raw_json = event.model_dump_json()
        data = json.loads(raw_json)

        expected_keys = {
            "id",
            "moment_id",
            "type",
            "half",
            "minute",
            "score_text",
            "importance",
            "confidence",
            "reasons",
            "moment_s",
            "clip",
            "overturned",
        }
        assert set(data.keys()) == expected_keys
        assert data["type"] == event_type
        assert set(data["clip"].keys()) == {"start_s", "end_s"}

    def test_reasons_serialization_shape(self):
        reason = Reason(signal="score", value=6, label="score +6")
        data = json.loads(reason.model_dump_json())
        assert set(data.keys()) == {"signal", "value", "label"}
        assert data["signal"] == "score"
        assert data["value"] == 6
        assert data["label"] == "score +6"


class TestExcitementCsvHelpers:
    """AC: Given excitement.csv helpers, values round-trip with one row per second."""

    def test_write_and_read_floats(self, tmp_path: Path):
        p = tmp_path / "excitement.csv"
        series = [0.12, 0.45, 0.89, 0.95, 0.33]

        write_excitement_csv(p, series)
        assert p.is_file()

        # Check raw rows: 1 header row + 5 data rows = 6 rows
        lines = p.read_text().strip().splitlines()
        assert len(lines) == 6
        assert lines[0] == "second,excitement"
        assert lines[1] == "0,0.120000"
        assert lines[5] == "4,0.330000"

        # Round-trip read
        loaded = read_excitement_csv(p)
        assert len(loaded) == len(series)
        for original, parsed in zip(series, loaded):
            assert parsed == pytest.approx(original, abs=1e-5)

    def test_write_and_read_entries(self, tmp_path: Path):
        p = tmp_path / "excitement_entries.csv"
        entries = [
            ExcitementEntry(second=0, excitement=0.05),
            ExcitementEntry(second=1, excitement=0.75),
            ExcitementEntry(second=2, excitement=0.98),
        ]

        write_excitement_csv(p, entries)
        loaded = read_excitement_entries(p)
        assert len(loaded) == 3
        assert loaded[0].second == 0
        assert loaded[0].excitement == pytest.approx(0.05, abs=1e-5)
        assert loaded[2].second == 2
        assert loaded[2].excitement == pytest.approx(0.98, abs=1e-5)
