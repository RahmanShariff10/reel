"""Crowd excitement per second (pipeline stage 6: ``audio``).

- Loudness: RMS level per second (dB) and a z-score against a rolling median / MAD
  over ``audio.excitement_window_s`` (default 5 minutes).
- Crowd sounds: PANNs CNN14 on 2 s windows with a 1 s hop → probabilities of the
  AudioSet classes Cheering, Applause and Crowd (looked up by name).
- Excitement: weighted combination of both, scaled to [0, 1].

Audio is read in blocks, so memory stays bounded on a 3.5-hour match.
"""

from __future__ import annotations

import csv
import math
import os
import tempfile
import typing
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

import numpy as np
import soundfile as sf

from reel.common.config import AudioConfig
from reel.common.logging import get_logger
from reel.common.models import Meta, read_model

if typing.TYPE_CHECKING:
    from reel.jobs.pipeline import PipelineContext, ProgressCallback

log = get_logger("audio.excitement")

CROWD_CLASSES = ("Cheering", "Applause", "Crowd")
COLUMNS = ["second", "excitement", "loudness_db", "loudness_z", "p_cheer", "p_applause", "p_crowd"]
PANNS_SR = 32000
PANNS_URL = "https://zenodo.org/record/3987831/files/Cnn14_mAP%3D0.431.pth?download=1"
PANNS_FILE = "Cnn14_mAP=0.431.pth"


class Tagger(Protocol):
    """Returns (n_windows, n_classes) probabilities for a batch of audio windows."""

    labels: Sequence[str]

    def tag(self, windows: np.ndarray) -> np.ndarray: ...


def resolve_indices(labels: Sequence[str], names: Sequence[str] = CROWD_CLASSES) -> list[int]:
    """Class indices by name; raises KeyError naming any class that is missing."""
    lookup = {name: i for i, name in enumerate(labels)}
    missing = [n for n in names if n not in lookup]
    if missing:
        raise KeyError(f"AudioSet classes missing from label list: {', '.join(missing)}")
    return [lookup[n] for n in names]


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading %s to %s", url, dest)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, suffix=".part")
    os.close(fd)
    try:
        urllib.request.urlretrieve(url, tmp)
        Path(tmp).replace(dest)
    finally:
        Path(tmp).unlink(missing_ok=True)


class PannsTagger:
    """PANNs CNN14 audio tagger on CPU; checkpoint cached in ``models_dir``."""

    def __init__(self, models_dir: Path) -> None:
        checkpoint = models_dir / PANNS_FILE
        if not checkpoint.is_file():
            _download(PANNS_URL, checkpoint)
        from panns_inference import AudioTagging, labels

        self.labels = list(labels)
        self._model = AudioTagging(checkpoint_path=str(checkpoint), device="cpu")

    def tag(self, windows: np.ndarray) -> np.ndarray:
        clipwise, _ = self._model.inference(windows.astype(np.float32))
        return np.asarray(clipwise)


def _rolling_median_mad(x: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray]:
    half = max(window // 2, 1)
    med = np.empty_like(x)
    mad = np.empty_like(x)
    for i in range(len(x)):
        seg = x[max(0, i - half) : i + half + 1]
        m = np.median(seg)
        med[i] = m
        mad[i] = np.median(np.abs(seg - m))
    return med, mad


def loudness_per_second(wav: Path, n_seconds: int) -> np.ndarray:
    """RMS level (dB) for each second, reading the file in blocks."""
    info = sf.info(str(wav))
    sr = info.samplerate
    db = np.full(n_seconds, -100.0)
    for i, block in enumerate(sf.blocks(str(wav), blocksize=sr, dtype="float32", fill_value=0.0)):
        if i >= n_seconds:
            break
        if block.ndim > 1:
            block = block.mean(axis=1)
        db[i] = 20 * math.log10(float(np.sqrt(np.mean(block**2))) + 1e-10)
    return db


def crowd_probabilities(
    wav: Path,
    n_seconds: int,
    tagger: Tagger,
    hop_s: int = 1,
    batch_windows: int = 32,
    progress: Callable[[float], None] | None = None,
) -> np.ndarray:
    """(n_seconds, 3) probabilities of Cheering, Applause, Crowd from 2 s windows.

    One window every ``hop_s`` seconds, centred on the seconds it covers; hop 2 halves
    the run time at the cost of time resolution.
    """
    idx = resolve_indices(tagger.labels)
    out = np.zeros((n_seconds, len(idx)))
    starts = list(range(0, n_seconds, hop_s))
    with sf.SoundFile(str(wav)) as f:
        if f.samplerate != PANNS_SR:
            raise ValueError(f"audio.wav must be {PANNS_SR} Hz, got {f.samplerate}")
        win = 2 * PANNS_SR
        for b in range(0, len(starts), batch_windows):
            secs = starts[b : b + batch_windows]
            windows = np.zeros((len(secs), win), np.float32)
            for j, s in enumerate(secs):
                centre = s + hop_s / 2
                f.seek(max(0, int((centre - 1.0) * PANNS_SR)))
                data = f.read(win, dtype="float32", always_2d=False)
                windows[j, : len(data)] = data if data.ndim == 1 else data.mean(axis=1)
            probs = tagger.tag(windows)[:, idx]
            for j, s in enumerate(secs):
                out[s : s + hop_s] = probs[j]
            if progress:
                progress(min(1.0, (b + len(secs)) / len(starts)))
    return out


def combine(loudness_z: np.ndarray, crowd: np.ndarray | None, cfg: AudioConfig) -> np.ndarray:
    """Excitement in [0, 1] from the loudness z-score and (optionally) crowd probabilities."""
    loud = np.clip(loudness_z / cfg.loudness_z_full, 0.0, 1.0)
    if crowd is None:
        return loud
    crowd_part = np.clip(crowd.sum(axis=1) / cfg.crowd_prob_full, 0.0, 1.0)
    total = cfg.weight_loudness + cfg.weight_crowd
    return (cfg.weight_loudness * loud + cfg.weight_crowd * crowd_part) / total


def compute_excitement(
    wav: Path | None,
    duration_s: float,
    cfg: AudioConfig,
    tagger: Tagger | None = None,
    progress: Callable[[float], None] | None = None,
) -> list[dict[str, float]]:
    """One row per second (ceil(duration) rows); all zeros when there is no audio."""
    n = max(1, math.ceil(duration_s))
    zeros = np.zeros(n)
    if wav is None or not wav.is_file():
        rows = zip(zeros, zeros, zeros, zeros, zeros, zeros)
        return [dict(zip(COLUMNS, (i, *r))) for i, r in enumerate(rows)]

    db = loudness_per_second(wav, n)
    med, mad = _rolling_median_mad(db, int(cfg.excitement_window_s))
    z = (db - med) / (1.4826 * np.maximum(mad, cfg.mad_floor_db))
    crowd = (
        crowd_probabilities(wav, n, tagger, cfg.panns_hop_s, progress=progress) if tagger else None
    )
    exc = combine(z, crowd, cfg)
    c = crowd if crowd is not None else np.zeros((n, 3))
    return [
        {
            "second": i,
            "excitement": round(float(exc[i]), 6),
            "loudness_db": round(float(db[i]), 3),
            "loudness_z": round(float(z[i]), 3),
            "p_cheer": round(float(c[i, 0]), 6),
            "p_applause": round(float(c[i, 1]), 6),
            "p_crowd": round(float(c[i, 2]), 6),
        }
        for i in range(n)
    ]


def write_excitement_rows(path: Path, rows: list[dict[str, float]]) -> None:
    """Atomic CSV write; ``excitement`` stays the second column for existing readers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    Path(tmp).replace(path)


def is_valid_audio(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    if not paths.excitement_csv.is_file() or not paths.meta_json.is_file():
        return False
    with open(paths.excitement_csv, newline="") as fh:
        rows = sum(1 for _ in fh) - 1
    return rows == max(1, math.ceil(read_model(paths.meta_json, Meta).duration_s))


def run_audio(
    ctx: PipelineContext,
    progress_cb: ProgressCallback | None = None,
    tagger: Tagger | None = None,
) -> None:
    paths, cfg = ctx.paths, ctx.config.audio
    meta = read_model(paths.meta_json, Meta)
    wav = paths.audio_wav if meta.has_audio else None
    if wav is not None and tagger is None and cfg.use_panns and ctx.config.signals.audio:
        tagger = PannsTagger(Path(ctx.config.models_dir))
    if not ctx.config.signals.audio:
        wav = None
    rows = compute_excitement(wav, meta.duration_s, cfg, tagger, progress_cb)
    write_excitement_rows(paths.excitement_csv, rows)
    log.info("Excitement written for %d seconds (PANNs %s)", len(rows), "on" if tagger else "off")
    if progress_cb:
        progress_cb(1.0)
