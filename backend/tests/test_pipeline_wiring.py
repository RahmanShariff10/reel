"""Tests for slice-22-pipeline-wiring.

Acceptance criteria:
- Synthetic video processed end to end by the worker: job done, reel_5min.mp4 exists,
  events.json contains the scheduled fours, sixes and wickets.
- The CLI produces the same events.json as the worker.
- A queued reel request for 3min runs only selection and render and ends done.
- signals.audio false: the audio stage does not run and the job still completes.
- --no-scorebox synthetic video: the job completes with moment events.
- summary.json has every field listed in ARCHITECTURE.md.

Shot labels come from the ground-truth schedule (CLIP can't read synthetic colour blocks).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from reel import cli
from reel.common.models import (
    Event,
    ReelPlan,
    Shot,
    Summary,
    read_excitement_csv,
    read_model,
    write_model,
)
from reel.common.paths import JobPaths
from reel.jobs import pipeline
from reel.jobs.store import create_job, create_reel_request, get_job, get_reel, init_db
from reel.jobs.worker import Worker
from tests.conftest import SyntheticMatch, make_synthetic_match


def schedule_labeller(schedule: dict):
    def run(ctx, progress_cb=None):
        shots = read_model(ctx.paths.shots_json, list[Shot])
        truth = schedule["shots"]
        out = []
        for s in shots:
            mid = (s.start_s + s.end_s) / 2
            scene = next(t for t in truth if t["start_s"] <= mid < t["end_s"])["scene"]
            out.append(s.model_copy(update={"label": scene, "label_source": "classifier"}))
        write_model(ctx.paths.shots_json, out)
        ctx.paths.shot_embeddings_npy.write_bytes(b"")

    return run


def stage(name: str) -> pipeline.Stage:
    return next(s for s in pipeline.DEFAULT_STAGES if s.name == name)


@pytest.fixture(scope="module")
def match75(tmp_path_factory) -> SyntheticMatch:
    return make_synthetic_match(tmp_path_factory.mktemp("m75"), duration_s=75.0)


@pytest.fixture(scope="module")
def worker_run(match75: SyntheticMatch, tmp_path_factory):
    data = tmp_path_factory.mktemp("worker_data")
    db = data / "reel.db"
    init_db(db)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(stage("classify_shots"), "runner", schedule_labeller(match75.schedule))
        job = create_job(db, input_path=str(match75.video))
        Worker(db_path=db, data_dir=data).run(once=True)
    return db, data, job.id


class TestEndToEnd:
    def test_worker_completes_with_events(self, worker_run, match75) -> None:
        db, data, job_id = worker_run
        assert get_job(db, job_id).status == "done"
        paths = JobPaths(job_id, data_dir=data)
        assert paths.reel_path("5min").is_file()
        events = read_model(paths.events_json, list[Event])
        expected = {"four", "six", "wicket"} & {
            d["outcome"] for d in match75.schedule["deliveries"]
        }
        assert expected and expected <= {e.type for e in events}
        reel = get_reel(db, job_id, "5min")
        assert reel.status == "done" and reel.event_ids

    def test_summary_fields(self, worker_run) -> None:
        db, data, job_id = worker_run
        s = read_model(JobPaths(job_id, data_dir=data).summary_json, Summary)
        assert s.teams and s.innings and s.deliveries_found > 0 and s.scorebox_found
        assert s.processing_s > 0
        assert set(s.stage_timings) == {st.name for st in pipeline.DEFAULT_STAGES}

    def test_cli_matches_worker(self, worker_run, match75, tmp_path, monkeypatch) -> None:
        db, data, job_id = worker_run
        monkeypatch.setenv("REEL_DATA_DIR", str(tmp_path))
        monkeypatch.setattr(stage("classify_shots"), "runner", schedule_labeller(match75.schedule))
        ctx = cli.run(match75.video)
        ours = read_model(ctx.paths.events_json, list[Event])
        theirs = read_model(JobPaths(job_id, data_dir=data).events_json, list[Event])
        key = lambda e: (e.type, e.moment_s, e.over_ball)  # noqa: E731
        assert [key(e) for e in ours] == [key(e) for e in theirs]


class TestRecut:
    def test_3min_runs_only_selection_and_render(self, worker_run, monkeypatch) -> None:
        db, data, job_id = worker_run

        def bomb(*args, **kwargs):
            raise AssertionError("analysis stages must not run for a re-cut")

        for st in pipeline.DEFAULT_STAGES:
            monkeypatch.setattr(st, "runner", bomb)
        create_reel_request(db, job_id, "3min")
        assert Worker(db_path=db, data_dir=data).process_one_reel()
        reel = get_reel(db, job_id, "3min")
        assert reel.status == "done", reel.error
        paths = JobPaths(job_id, data_dir=data)
        assert paths.reel_path("3min").is_file()
        assert read_model(paths.reel_plan_path("3min"), ReelPlan).mode == "3min"


class TestSignals:
    def test_audio_off(self, worker_run, tmp_path, monkeypatch, match75) -> None:
        db, data, job_id = worker_run
        monkeypatch.setenv("REEL_DATA_DIR", str(data))
        monkeypatch.setattr(
            stage("audio"),
            "runner",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("audio ran")),
        )
        cfg = tmp_path / "off.yaml"
        cfg.write_text(yaml.safe_dump({"signals": {"audio": False}}))
        ctx = cli.run(match75.video, config_file=cfg, job_id=job_id)
        assert get_job(db, job_id).status == "done"
        assert set(read_excitement_csv(ctx.paths.excitement_csv)) == {0.0}

    def test_no_scorebox_gives_moments(self, tmp_path, monkeypatch) -> None:
        m = make_synthetic_match(tmp_path / "nsb", duration_s=45.0, scorebox=False)
        monkeypatch.setenv("REEL_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setattr(stage("classify_shots"), "runner", schedule_labeller(m.schedule))
        # Synthetic bursts are pink noise, which PANNs (rightly) doesn't call cheering.
        cfg = tmp_path / "loudness.yaml"
        cfg.write_text(yaml.safe_dump({"audio": {"use_panns": False}}))
        ctx = cli.run(m.video, config_file=cfg)
        events = read_model(ctx.paths.events_json, list[Event])
        assert events and {e.type for e in events} == {"moment"}
        assert ctx.paths.reel_path("5min").is_file()
        assert not read_model(ctx.paths.summary_json, Summary).scorebox_found


def test_cli_main_rejects_missing_file(tmp_path: Path, capsys) -> None:
    assert cli.main(["run", str(tmp_path / "missing.mp4")]) == 2
