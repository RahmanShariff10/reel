"""Standardized file and directory path resolution for Reel jobs.

Every stage file and folder listed in ARCHITECTURE.md "Job directory" is
accessible via properties on :class:`JobPaths`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reel.common.config import load_config


class JobPaths:
    """Resolves all file and directory paths for a given job ID.

    Parameters
    ----------
    job_id : str
        The unique identifier for the job.
    data_dir : Path | str | None, optional
        Root data directory. Defaults to ``load_config().data_dir``.
    """

    def __init__(self, job_id: str, data_dir: Path | str | None = None) -> None:
        self.job_id = str(job_id)
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            self._data_dir = Path(load_config().data_dir)
        self._root = self._data_dir / "jobs" / self.job_id

    @property
    def root(self) -> Path:
        """Root directory for this job: {data_dir}/jobs/{job_id}/."""
        return self._root

    # ---- Stage 1: Ingest ----

    @property
    def input_file(self) -> Path:
        """Default path for uploaded input video."""
        return self._root / "input.mp4"

    def input_path(self, ext: str = "mp4") -> Path:
        """Path for input video with custom extension."""
        clean_ext = ext.lstrip(".")
        return self._root / f"input.{clean_ext}"

    @property
    def meta_json(self) -> Path:
        return self._root / "meta.json"

    @property
    def meta(self) -> Path:
        return self.meta_json

    @property
    def audio_wav(self) -> Path:
        return self._root / "audio.wav"

    @property
    def audio(self) -> Path:
        return self.audio_wav

    # ---- Stage 2: Locate Scorebox ----

    @property
    def scorebox_json(self) -> Path:
        return self._root / "scorebox.json"

    @property
    def scorebox(self) -> Path:
        return self.scorebox_json

    @property
    def scorebox_preview_jpg(self) -> Path:
        return self._root / "scorebox_preview.jpg"

    @property
    def scorebox_preview(self) -> Path:
        return self.scorebox_preview_jpg

    # ---- Stage 3: Scan Pass ----

    @property
    def shots_json(self) -> Path:
        return self._root / "shots.json"

    @property
    def shots(self) -> Path:
        return self.shots_json

    @property
    def keyframes_dir(self) -> Path:
        return self._root / "keyframes"

    @property
    def keyframes(self) -> Path:
        return self.keyframes_dir

    @property
    def score_crops_dir(self) -> Path:
        return self._root / "score_crops"

    @property
    def score_crops(self) -> Path:
        return self.score_crops_dir

    # ---- Stage 4: Read Score ----

    @property
    def score_readings_json(self) -> Path:
        return self._root / "score_readings.json"

    @property
    def score_readings(self) -> Path:
        return self.score_readings_json

    @property
    def score_timeline_json(self) -> Path:
        return self._root / "score_timeline.json"

    @property
    def score_timeline(self) -> Path:
        return self.score_timeline_json

    @property
    def score_events_json(self) -> Path:
        return self._root / "score_events.json"

    @property
    def score_events(self) -> Path:
        return self.score_events_json

    # ---- Stage 5: Classify Shots ----

    @property
    def shot_embeddings_npy(self) -> Path:
        return self._root / "shot_embeddings.npy"

    @property
    def shot_embeddings(self) -> Path:
        return self.shot_embeddings_npy

    # ---- Stage 6: Audio Excitement ----

    @property
    def excitement_csv(self) -> Path:
        return self._root / "excitement.csv"

    @property
    def excitement(self) -> Path:
        return self.excitement_csv

    # ---- Stage 7: Deliveries ----

    @property
    def deliveries_json(self) -> Path:
        return self._root / "deliveries.json"

    @property
    def deliveries(self) -> Path:
        return self.deliveries_json

    # ---- Stage 8: Highlights & Events ----

    @property
    def events_json(self) -> Path:
        return self._root / "events.json"

    @property
    def events(self) -> Path:
        return self.events_json

    def reel_plan_path(self, mode: str = "5min") -> Path:
        """Path to reel_plan_<mode>.json."""
        return self._root / f"reel_plan_{mode}.json"

    def reel_plan_json(self, mode: str = "5min") -> Path:
        """Alias for reel_plan_path."""
        return self.reel_plan_path(mode)

    @property
    def reel_plan(self) -> Path:
        """Default (5min) reel plan file."""
        return self.reel_plan_path("5min")

    # ---- Stage 9: Render & Summary ----

    @property
    def clips_dir(self) -> Path:
        return self._root / "clips"

    @property
    def clips(self) -> Path:
        return self.clips_dir

    def reel_path(self, mode: str = "5min") -> Path:
        """Path to reel_<mode>.mp4."""
        return self._root / f"reel_{mode}.mp4"

    def reel_mp4(self, mode: str = "5min") -> Path:
        """Alias for reel_path."""
        return self.reel_path(mode)

    @property
    def reel(self) -> Path:
        """Default (5min) reel video file."""
        return self.reel_path("5min")

    @property
    def title_png(self) -> Path:
        return self._root / "title.png"

    @property
    def title(self) -> Path:
        return self.title_png

    @property
    def summary_json(self) -> Path:
        return self._root / "summary.json"

    @property
    def summary(self) -> Path:
        return self.summary_json

    # ---- Flexible / Dynamic Lookup ----

    def __getitem__(self, item: str) -> Path:
        """Allow dict-like lookup e.g. paths['meta.json']."""
        clean = item.strip().rstrip("/")
        if "<mode>" in clean:
            clean = clean.replace("<mode>", "5min")
        return self._root / clean

    def __getattr__(self, name: str) -> Any:
        """Allow attribute-style lookup for raw filenames like getattr(paths, 'meta.json')."""
        clean = name.rstrip("/")
        if clean.endswith((".json", ".jpg", ".png", ".wav", ".mp4", ".csv", ".npy")):
            return self._root / clean
        if clean in ("keyframes", "score_crops", "clips"):
            return self._root / clean
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def ensure_job_dir(self) -> Path:
        """Create the job root directory if it does not exist."""
        self._root.mkdir(parents=True, exist_ok=True)
        return self._root
