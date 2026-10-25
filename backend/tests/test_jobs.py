"""Tests for slice-04-job-store-worker: SQLite store, worker loop, pipeline runner.

Acceptance criteria:
- Given a new job, when create_job is called, then its status is queued and progress 0.
- Given a queued job, when worker --once runs, then the job ends done with progress 100
  and every placeholder stage ran in order.
- Given a stage whose output files already exist and are valid, when the pipeline runs,
  then that stage is not invoked.
- Given a stage that raises, when the pipeline runs, then the job is failed, the error
  message is stored, and later stages do not run.
- Given two workers claiming at the same time, then no job is claimed twice.
- Given a job left running by a killed worker, when a worker starts, then the job is
  re-queued and resumes, skipping completed stages.
- Given a running job, then progress never decreases.
- Given a (job, mode) pair, then at most one Reel row exists.
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path

import pytest

from reel.common.models import Meta, write_model
from reel.common.paths import JobPaths
from reel.jobs.pipeline import DEFAULT_STAGES, PipelineContext, Stage, run_pipeline
from reel.jobs.store import (
    claim_next_job,
    create_job,
    create_reel_request,
    get_job,
    get_reel,
    init_db,
    list_reels_for_job,
    requeue_stale_jobs,
    update_progress,
)
from reel.jobs.worker import Worker, main
from tests.fixtures.make_synthetic import generate_synthetic_video


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "test_reel.db"
    init_db(p)
    return p


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# AC 1: New job is queued with progress 0
# ---------------------------------------------------------------------------


class TestCreateJob:
    def test_new_job_status_and_progress(self, db_path: Path):
        job = create_job(db_path, input_path="/path/to/match.mp4", filename="match.mp4")
        assert job.status == "queued"
        assert job.progress == 0.0
        assert job.filename == "match.mp4"
        assert job.stage is None
        assert job.started_at is None
        assert job.finished_at is None
        assert job.error is None

        fetched = get_job(db_path, job.id)
        assert fetched is not None
        assert fetched.id == job.id
        assert fetched.status == "queued"
        assert fetched.progress == 0.0


# ---------------------------------------------------------------------------
# AC 2: Worker --once completes queued job with progress 100
# ---------------------------------------------------------------------------


class TestWorkerOnce:
    def test_worker_once_completes_job_and_all_placeholder_stages(
        self, db_path: Path, data_dir: Path
    ):
        input_vid, _ = generate_synthetic_video(data_dir, duration_s=2.0)

        job = create_job(
            db_path,
            input_path=str(input_vid),
            filename="sample.mp4",
        )

        worker = Worker(db_path=db_path, data_dir=data_dir)
        worker.run(once=True)

        finished_job = get_job(db_path, job.id)
        assert finished_job is not None
        assert finished_job.status == "done"
        assert finished_job.progress == 100.0
        assert finished_job.finished_at is not None
        assert finished_job.error is None

        # Verify output files from placeholder stages exist
        paths = JobPaths(job.id, data_dir=data_dir)
        assert paths.meta_json.is_file()
        assert paths.audio_wav.is_file()
        assert paths.scorebox_json.is_file()
        assert paths.scorebox_preview_jpg.is_file()
        assert paths.shots_json.is_file()
        assert paths.score_readings_json.is_file()
        assert paths.score_timeline_json.is_file()
        assert paths.score_events_json.is_file()
        assert paths.shot_embeddings_npy.is_file()
        assert paths.excitement_csv.is_file()
        assert paths.deliveries_json.is_file()
        assert paths.events_json.is_file()
        assert paths.reel_plan_path("5min").is_file()
        assert paths.reel_path("5min").is_file()
        assert paths.summary_json.is_file()

    def test_cli_worker_main_once(self, db_path: Path, data_dir: Path):
        input_vid, _ = generate_synthetic_video(data_dir, duration_s=2.0)
        job = create_job(db_path, input_path=str(input_vid))
        ret = main(["--once", "--db-path", str(db_path), "--data-dir", str(data_dir)])
        assert ret == 0

        finished = get_job(db_path, job.id)
        assert finished is not None
        assert finished.status == "done"
        assert finished.progress == 100.0


# ---------------------------------------------------------------------------
# AC 3: Stages with valid outputs are skipped
# ---------------------------------------------------------------------------


class TestStageSkipping:
    def test_stage_not_invoked_when_output_is_valid(self, db_path: Path, data_dir: Path):
        job = create_job(db_path, input_path="test.mp4")
        paths = JobPaths(job.id, data_dir=data_dir)
        paths.ensure_job_dir()

        # Pre-create valid meta.json so ingest is already valid
        meta = Meta(duration_s=50.0, width=1280, height=720, fps=25.0)
        write_model(paths.meta_json, meta)
        paths.audio_wav.write_bytes(b"EXISTING_WAV")

        invoked_stages = []

        def mock_runner(name: str):
            def _runner(ctx, cb=None):
                invoked_stages.append(name)
                # Run the actual placeholder so downstream stages don't fail
                for s in DEFAULT_STAGES:
                    if s.name == name:
                        s.runner(ctx)
                        break

            return _runner

        custom_stages = [
            Stage(
                name=s.name,
                weight=s.weight,
                validator=s.validator,
                runner=mock_runner(s.name),
            )
            for s in DEFAULT_STAGES
        ]

        ctx = PipelineContext(
            job_id=job.id,
            db_path=db_path,
            paths=paths,
            input_path=Path("test.mp4"),
        )
        claim_next_job(db_path)
        run_pipeline(ctx, stages=custom_stages)

        # 'ingest' must NOT be in invoked_stages because its outputs existed and were valid!
        assert "ingest" not in invoked_stages
        # Other stages should have run
        assert "locate_scorebox" in invoked_stages
        assert "render" in invoked_stages

        final_job = get_job(db_path, job.id)
        assert final_job is not None
        assert final_job.status == "done"
        assert final_job.progress == 100.0


# ---------------------------------------------------------------------------
# AC 4: Failing stage marks job failed and aborts later stages
# ---------------------------------------------------------------------------


class TestStageFailure:
    def test_stage_raises_marks_job_failed_and_aborts_later_stages(
        self, db_path: Path, data_dir: Path
    ):
        input_vid, _ = generate_synthetic_video(data_dir, duration_s=2.0)
        job = create_job(db_path, input_path=str(input_vid))
        paths = JobPaths(job.id, data_dir=data_dir)
        paths.ensure_job_dir()

        executed_stages = []

        def failing_scan(ctx, cb=None):
            executed_stages.append("scan")
            raise RuntimeError("Corrupt video frame at second 12.5")

        def mock_runner(name: str):
            def _runner(ctx, cb=None):
                executed_stages.append(name)
                for s in DEFAULT_STAGES:
                    if s.name == name:
                        s.runner(ctx)
                        break

            return _runner

        custom_stages = [
            Stage(
                name="ingest",
                weight=10.0,
                validator=lambda _: False,
                runner=mock_runner("ingest"),
            ),
            Stage(
                name="locate_scorebox",
                weight=10.0,
                validator=lambda _: False,
                runner=mock_runner("locate_scorebox"),
            ),
            Stage(name="scan", weight=20.0, validator=lambda _: False, runner=failing_scan),
            Stage(
                name="read_score",
                weight=10.0,
                validator=lambda _: False,
                runner=mock_runner("read_score"),
            ),
        ]

        ctx = PipelineContext(
            job_id=job.id,
            db_path=db_path,
            paths=paths,
            input_path=input_vid,
        )
        claim_next_job(db_path)

        with pytest.raises(RuntimeError, match="Corrupt video frame"):
            run_pipeline(ctx, stages=custom_stages)

        # Ingest and locate_scorebox ran, scan raised, read_score did NOT run
        assert executed_stages == ["ingest", "locate_scorebox", "scan"]
        assert "read_score" not in executed_stages

        failed_job = get_job(db_path, job.id)
        assert failed_job is not None
        assert failed_job.status == "failed"
        assert "Corrupt video frame" in str(failed_job.error)
        assert failed_job.finished_at is not None


# ---------------------------------------------------------------------------
# AC 5: Atomic job claiming by concurrent workers
# ---------------------------------------------------------------------------


class TestConcurrentClaiming:
    def test_no_job_claimed_twice_by_concurrent_workers(self, db_path: Path):
        num_jobs = 15
        job_ids = [create_job(db_path, input_path=f"vid_{i}.mp4").id for i in range(num_jobs)]

        claimed_jobs: list[str] = []

        def claim_worker():
            results = []
            while True:
                j = claim_next_job(db_path)
                if not j:
                    break
                results.append(j.id)
            return results

        num_threads = 5
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(claim_worker) for _ in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                claimed_jobs.extend(f.result())

        # Every job must be claimed exactly once
        assert sorted(claimed_jobs) == sorted(job_ids)
        assert len(claimed_jobs) == len(set(claimed_jobs))


# ---------------------------------------------------------------------------
# AC 6: Requeue stale running jobs on worker restart
# ---------------------------------------------------------------------------


class TestStaleJobRequeue:
    def test_running_job_is_requeued_on_worker_startup(self, db_path: Path, data_dir: Path):
        job = create_job(db_path, input_path="stale.mp4")

        # Simulate job claimed and running
        claimed = claim_next_job(db_path)
        assert claimed is not None
        assert claimed.id == job.id

        # Pre-fill ingest and locate_scorebox so they will be skipped upon resumption
        paths = JobPaths(job.id, data_dir=data_dir)
        paths.ensure_job_dir()
        meta = Meta(duration_s=100.0, width=1280, height=720, fps=25.0)
        write_model(paths.meta_json, meta)
        paths.audio_wav.write_bytes(b"AUDIO")

        # Worker starts up: requeue_stale_jobs resets running jobs to queued
        requeued_count = requeue_stale_jobs(db_path)
        assert requeued_count == 1

        requeued_job = get_job(db_path, job.id)
        assert requeued_job is not None
        assert requeued_job.status == "queued"

        # Worker runs and finishes the job
        worker = Worker(db_path=db_path, data_dir=data_dir)
        worker.run(once=True)

        resumed_job = get_job(db_path, job.id)
        assert resumed_job is not None
        assert resumed_job.status == "done"
        assert resumed_job.progress == 100.0


# ---------------------------------------------------------------------------
# AC 7: Progress never decreases
# ---------------------------------------------------------------------------


class TestProgressNeverDecreases:
    def test_update_progress_monotonically_increases(self, db_path: Path):
        job = create_job(db_path, input_path="prog.mp4")
        claim_next_job(db_path)

        update_progress(db_path, job.id, "scan", 40.0)
        assert get_job(db_path, job.id).progress == 40.0

        # Attempt to set lower progress
        update_progress(db_path, job.id, "scan", 25.0)
        assert get_job(db_path, job.id).progress == 40.0

        # Attempt to set 0.0
        update_progress(db_path, job.id, "scan", 0.0)
        assert get_job(db_path, job.id).progress == 40.0

        # Advance progress forward
        update_progress(db_path, job.id, "audio", 65.0)
        assert get_job(db_path, job.id).progress == 65.0


# ---------------------------------------------------------------------------
# AC 8: At most one Reel row per (job, mode) pair
# ---------------------------------------------------------------------------


class TestReelUniqueness:
    def test_at_most_one_reel_row_per_job_mode(self, db_path: Path):
        job = create_job(db_path, input_path="reel_test.mp4")

        # Create first request for 5min
        r1 = create_reel_request(db_path, job.id, "5min")
        assert r1.job_id == job.id
        assert r1.mode == "5min"
        assert r1.status == "queued"

        # Create request for 10min
        r2 = create_reel_request(db_path, job.id, "10min")
        assert r2.mode == "10min"

        # Re-request 5min with excluded events
        r3 = create_reel_request(db_path, job.id, "5min", exclude_event_ids=["ev-02"])
        assert r3.exclude_event_ids == ["ev-02"]

        reels = list_reels_for_job(db_path, job.id)
        # Exactly 2 reels: one for 5min and one for 10min
        assert len(reels) == 2
        modes = [r.mode for r in reels]
        assert sorted(modes) == ["10min", "5min"]

        r_5min = get_reel(db_path, job.id, "5min")
        assert r_5min is not None
        assert r_5min.exclude_event_ids == ["ev-02"]
