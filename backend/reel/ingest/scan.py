"""Pipeline stage 3: ``scan`` — the only full decode of the video.

One ffmpeg process, two outputs:

(a) low-resolution frames at ``scan.low_res_fps``, piped into Python for camera-cut
    detection and one keyframe (middle frame) per shot → ``shots.json``, ``keyframes/``;
(b) full-resolution crops of the score box at ``scan.score_crop_fps`` → ``score_crops/``,
    named ``crop_<milliseconds>.png`` (skipped when the score box was not found).

Frames are streamed, never held for the whole video.
"""

from __future__ import annotations

import shutil
import subprocess
import typing
from pathlib import Path

import cv2
import numpy as np

from reel.common.logging import get_logger
from reel.common.models import Meta, Scorebox, Shot, is_valid, read_model, write_model
from reel.ingest.probe import find_binary
from reel.shots.cuts import CutDetector

if typing.TYPE_CHECKING:
    from reel.jobs.pipeline import PipelineContext, ProgressCallback

log = get_logger("ingest.scan")

MAX_SHOT_BUFFER = 400  # frames kept per shot before thinning (bounds memory on long shots)


def crop_name(time_s: float) -> str:
    return f"crop_{round(time_s * 1000):08d}.png"


def crop_time(path: Path) -> float:
    """Timestamp in seconds encoded in a score-crop filename."""
    return int(path.stem.split("_")[1]) / 1000


def _input_file(ctx: PipelineContext) -> Path:
    if ctx.input_path and Path(ctx.input_path).is_file():
        return Path(ctx.input_path)
    if ctx.paths.input_file.is_file():
        return ctx.paths.input_file
    raise ValueError("Not a valid video file")


def is_valid_scan(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    return (
        is_valid(paths.shots_json, list[Shot])
        and paths.keyframes_dir.is_dir()
        and paths.score_crops_dir.is_dir()
    )


class _ShotWriter:
    """Tracks the current shot's frames and writes its middle frame as the keyframe."""

    def __init__(self, keyframes_dir: Path, fps: float) -> None:
        self.dir = keyframes_dir
        self.fps = fps
        self.shots: list[Shot] = []
        self._start = 0
        self._frames: list[tuple[int, np.ndarray]] = []

    def add(self, index: int, frame: np.ndarray) -> None:
        self._frames.append((index, frame))
        if len(self._frames) > MAX_SHOT_BUFFER:
            self._frames = self._frames[::2]

    def close(self, end_index: int, end_s: float) -> None:
        """End the current shot just before ``end_index``; later frames start the next."""
        current = [f for f in self._frames if f[0] < end_index]
        if not current:
            return
        shot_id = len(self.shots)
        mid = (self._start + end_index - 1) / 2
        _, frame = min(current, key=lambda f: abs(f[0] - mid))
        name = f"shot_{shot_id:05d}.jpg"
        cv2.imwrite(str(self.dir / name), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        start_s = round(self._start / self.fps, 3)
        self.shots.append(Shot(
            id=shot_id, start_s=start_s, end_s=round(end_s, 3),
            duration_s=round(end_s - start_s, 3), keyframe_path=f"keyframes/{name}",
        ))
        self._start = end_index
        self._frames = [f for f in self._frames if f[0] >= end_index]


def run_scan(ctx: PipelineContext, progress_cb: ProgressCallback | None = None) -> None:
    paths, cfg = ctx.paths, ctx.config.scan
    video = _input_file(ctx)
    meta = read_model(paths.meta_json, Meta)
    scorebox = read_model(paths.scorebox_json, Scorebox) if paths.scorebox_json.is_file() else None

    for d in (paths.keyframes_dir, paths.score_crops_dir):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)

    lo_w = cfg.keyframe_width
    lo_h = max(2, round(meta.height * lo_w / meta.width / 2) * 2)
    fps = float(cfg.low_res_fps)

    graph = f"[0:v]fps={cfg.low_res_fps},scale={lo_w}:{lo_h}[lo]"
    crop_out: list[str] = []
    if scorebox and scorebox.found and scorebox.box:
        x, y, w, h = scorebox.box
        graph = (
            f"[0:v]split=2[a][b];[a]fps={cfg.low_res_fps},scale={lo_w}:{lo_h}[lo];"
            f"[b]fps={cfg.score_crop_fps},format=rgb24,crop={w}:{h}:{x}:{y}[sc]"
        )
        crop_out = ["-map", "[sc]", "-start_number", "0", "-f", "image2",
                    str(paths.score_crops_dir / "%07d.png")]

    cmd = [
        find_binary("ffmpeg"), "-v", "error", "-nostdin", "-i", str(video),
        "-filter_complex", graph,
        "-map", "[lo]", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1",
        *crop_out,
    ]
    log.info("Scanning %s (one decode pass)", video.name)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None

    detector = CutDetector(fps, cfg.cut_threshold, cfg.min_shot_s)
    writer = _ShotWriter(paths.keyframes_dir, fps)
    frame_bytes = lo_w * lo_h * 3
    expected = max(1, int(meta.duration_s * fps))
    index = 0
    while True:
        buf = proc.stdout.read(frame_bytes)
        if len(buf) < frame_bytes:
            break
        frame = np.frombuffer(buf, np.uint8).reshape(lo_h, lo_w, 3)
        writer.add(index, frame)
        for cut in detector.process(index, frame):
            writer.close(cut, cut / fps)
        index += 1
        if progress_cb and index % 100 == 0:
            progress_cb(min(0.99, index / expected))
    stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
    if proc.wait() != 0:
        raise RuntimeError(f"Scan failed: {stderr.strip()}")
    for cut in detector.flush(max(index - 1, 0)):
        writer.close(cut, cut / fps)
    writer.close(index, meta.duration_s)

    # Name crops by timestamp: frame k of the crop output is at k / score_crop_fps
    for f in sorted(paths.score_crops_dir.glob("[0-9]*.png")):
        f.rename(f.with_name(crop_name(int(f.stem) / cfg.score_crop_fps)))

    write_model(paths.shots_json, writer.shots)
    log.info("Scan done: %d frames, %d shots, %d score crops", index, len(writer.shots),
             len(list(paths.score_crops_dir.glob("crop_*.png"))))
    if progress_cb:
        progress_cb(1.0)
