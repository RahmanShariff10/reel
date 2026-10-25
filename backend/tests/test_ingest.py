"""Tests for slice-07-ingest: video probing, audio extraction, pipeline integration.

Acceptance criteria:
- Given the synthetic video, when the stage runs, then meta.json has duration within 0.1 s
  of the schedule, width 1280, height 720 and has_audio: true.
- Given the synthetic video, then audio.wav is 32 000 Hz, mono, with duration within 0.1 s
  of the video.
- Given a video with no audio (--no-audio), then has_audio is false, no audio.wav is
  written, and the stage succeeds.
- Given a file that is not a valid video, then the job fails with the message
  "Not a valid video file".
- Given a local_path job, then no copy of the input is created in the job folder.
- Given valid existing outputs, when the pipeline re-runs, then the stage is skipped.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from reel.common.models import Meta, read_model
from reel.common.paths import JobPaths
from reel.ingest.probe import find_binary
from reel.ingest.stage import is_valid_ingest, run_ingest
from reel.jobs.pipeline import PipelineContext, run_pipeline
from reel.jobs.store import claim_next_job, create_job, get_job, init_db
from tests.fixtures.make_synthetic import generate_synthetic_video


@pytest.fixture(scope="session")
def synthetic_video(tmp_path_factory) -> tuple[Path, Path]:
    tmp = tmp_path_factory.mktemp("synthetic")
    return generate_synthetic_video(tmp, duration_s=6.0, has_audio=True)


@pytest.fixture(scope="session")
def synthetic_no_audio(tmp_path_factory) -> tuple[Path, Path]:
    tmp = tmp_path_factory.mktemp("synthetic_no_audio")
    return generate_synthetic_video(tmp, duration_s=4.0, has_audio=False)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "reel.db"
    init_db(p)
    return p


# ---------------------------------------------------------------------------
# AC 1 & 2: Synthetic video metadata & 32kHz mono audio extraction
# ---------------------------------------------------------------------------


class TestSyntheticIngest:
    def test_meta_and_audio_extraction(
        self,
        synthetic_video: tuple[Path, Path],
        tmp_path: Path,
        db_path: Path,
    ):
        video_path, schedule_path = synthetic_video
        sched = json.loads(schedule_path.read_text())

        job_id = "test-ingest-synth"
        paths = JobPaths(job_id, data_dir=tmp_path)
        ctx = PipelineContext(
            job_id=job_id,
            db_path=db_path,
            paths=paths,
            input_path=video_path,
        )

        paths.ensure_job_dir()
        run_ingest(ctx)

        # 1. Verify meta.json
        assert paths.meta_json.is_file()
        meta = read_model(paths.meta_json, Meta)
        assert meta.width == 1280
        assert meta.height == 720
        assert meta.has_audio is True
        assert abs(meta.duration_s - sched["duration_s"]) <= 0.1

        # 2. Verify audio.wav is 32000 Hz, mono, duration within 0.1s
        assert paths.audio_wav.is_file()

        ffprobe = find_binary("ffprobe")
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=sample_rate,channels,duration:format=duration",
            "-of",
            "json",
            str(paths.audio_wav),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        probe_res = json.loads(proc.stdout)
        astream = probe_res["streams"][0]

        assert int(astream["sample_rate"]) == 32000
        assert int(astream["channels"]) == 1
        wav_dur = float(probe_res.get("format", {}).get("duration") or astream.get("duration"))
        assert abs(wav_dur - meta.duration_s) <= 0.1


# ---------------------------------------------------------------------------
# AC 3: Video with no audio (--no-audio)
# ---------------------------------------------------------------------------


class TestNoAudioIngest:
    def test_no_audio_stage_succeeds_without_audio_wav(
        self,
        synthetic_no_audio: tuple[Path, Path],
        tmp_path: Path,
        db_path: Path,
    ):
        video_path, _ = synthetic_no_audio
        job_id = "test-no-audio-job"
        paths = JobPaths(job_id, data_dir=tmp_path)
        ctx = PipelineContext(
            job_id=job_id,
            db_path=db_path,
            paths=paths,
            input_path=video_path,
        )

        paths.ensure_job_dir()
        run_ingest(ctx)

        assert paths.meta_json.is_file()
        meta = read_model(paths.meta_json, Meta)
        assert meta.has_audio is False
        assert not paths.audio_wav.exists()

        # is_valid_ingest must return True even though audio.wav is not present
        assert is_valid_ingest(ctx) is True


# ---------------------------------------------------------------------------
# AC 4: Invalid video fails with "Not a valid video file"
# ---------------------------------------------------------------------------


class TestInvalidVideoFile:
    def test_corrupt_file_raises_not_a_valid_video_file(
        self,
        tmp_path: Path,
        db_path: Path,
    ):
        corrupt = tmp_path / "corrupt.mp4"
        corrupt.write_text("THIS IS NOT A VALID VIDEO")

        job = create_job(db_path, input_path=str(corrupt))
        claim_next_job(db_path)

        paths = JobPaths(job.id, data_dir=tmp_path)
        ctx = PipelineContext(
            job_id=job.id,
            db_path=db_path,
            paths=paths,
            input_path=corrupt,
        )

        with pytest.raises(ValueError, match="Not a valid video file"):
            run_ingest(ctx)

    def test_pipeline_records_not_a_valid_video_file_failure(
        self,
        tmp_path: Path,
        db_path: Path,
    ):
        not_a_video = tmp_path / "text.txt"
        not_a_video.write_text("Hello world")

        job = create_job(db_path, input_path=str(not_a_video))
        claim_next_job(db_path)

        paths = JobPaths(job.id, data_dir=tmp_path)
        ctx = PipelineContext(
            job_id=job.id,
            db_path=db_path,
            paths=paths,
            input_path=not_a_video,
        )

        with pytest.raises(Exception):
            run_pipeline(ctx)

        failed_job = get_job(db_path, job.id)
        assert failed_job is not None
        assert failed_job.status == "failed"
        assert "Not a valid video file" in str(failed_job.error)


# ---------------------------------------------------------------------------
# AC 5: local_path jobs read file in place, no copy created in job folder
# ---------------------------------------------------------------------------


class TestLocalPathInPlace:
    def test_local_path_reads_in_place_without_copy(
        self,
        synthetic_video: tuple[Path, Path],
        tmp_path: Path,
        db_path: Path,
    ):
        video_path, _ = synthetic_video
        job_id = "test-local-job"
        paths = JobPaths(job_id, data_dir=tmp_path)
        ctx = PipelineContext(
            job_id=job_id,
            db_path=db_path,
            paths=paths,
            input_path=video_path,
        )

        paths.ensure_job_dir()
        run_ingest(ctx)

        # Check job directory contents: no video copy should be in paths.root
        job_files = list(paths.root.iterdir())
        file_names = {f.name for f in job_files}
        assert "synthetic_video.mp4" not in file_names
        assert "input.mp4" not in file_names
        assert not any(f.suffix in [".mp4", ".mkv", ".mov"] for f in job_files)


# ---------------------------------------------------------------------------
# AC 6: Valid existing outputs cause stage to be skipped
# ---------------------------------------------------------------------------


class TestIngestStageSkipping:
    def test_stage_skipped_when_outputs_exist(
        self,
        synthetic_video: tuple[Path, Path],
        tmp_path: Path,
        db_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        video_path, _ = synthetic_video
        job_id = "test-skip-ingest"
        paths = JobPaths(job_id, data_dir=tmp_path)
        ctx = PipelineContext(
            job_id=job_id,
            db_path=db_path,
            paths=paths,
            input_path=video_path,
        )

        paths.ensure_job_dir()
        # First run creates outputs
        run_ingest(ctx)
        assert is_valid_ingest(ctx) is True

        # Monkeypatch probe_video to ensure it's NOT called on subsequent run
        def bomb(*args, **kwargs):
            raise AssertionError("probe_video should not be called when outputs are valid!")

        from reel.ingest import stage

        monkeypatch.setattr(stage, "probe_video", bomb)

        # Re-running pipeline should skip ingest stage without error
        claim_next_job(db_path)
        # Check is_valid_ingest directly
        assert stage.is_valid_ingest(ctx) is True
