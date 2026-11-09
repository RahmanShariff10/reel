"""Real-match assumption check (slice 38). A throwaway measuring script.

Measures three design assumptions on real matches and writes numbers only, never frames
or broadcast text beyond team codes, to ``eval/reports/assumptions.md``:

- A1, clock: a screen position shows a clock that advances with the video;
- A2, replays: the score graphic hides during replays but not during live play;
- A3, audio: crowd-excitement peaks line up with goals and shots on target.

It also reports each match's commentary language.

Run it on the laptop whose Hugging Face account was approved for SoccerNet::

    uv run --project backend python -m eval.check_assumptions \\
        --manifest eval/manifests/assumption_games.yaml \\
        --videos data/soccernet/videos-720p --labels eval/soccernet

Only ``game`` is required per manifest entry, because the language isn't known yet. Each game
needs ``1_720p.mkv`` and ``2_720p.mkv`` under ``--videos`` and its label files (public, from
``SoccerNet/SN-Labels``) under ``--labels``.
"""

from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np
import yaml
from reel.audio.excitement import PannsTagger, Tagger, compute_excitement
from reel.common.config import AudioConfig, MomentsConfig, ReelConfig, ScoreboardConfig, load_config
from reel.ingest.frames import grab_frame
from reel.ingest.probe import extract_audio, find_binary, probe_video
from reel.scoreboard.ocr import OcrItem, read_text
from scipy.signal import find_peaks

from eval.prepare import find_half_files
from eval.soccernet import CameraLabel, Label, load_camera_labels, load_labels

EVAL_DIR = Path(__file__).parent
REPORT_PATH = EVAL_DIR / "reports" / "assumptions.md"

# Clock token: M:SS, MM:SS or MMM:SS. "2:1" is a score, because seconds always have two digits.
_CLOCK_RE = re.compile(r"(?<![\d:.])(\d{1,3}):([0-5]\d)(?![\d:])")

Rect = tuple[int, int, int, int]
FrameReader = Callable[[int, float], np.ndarray | None]
TextReader = Callable[[np.ndarray], list[OcrItem]]

PEAK_TOLERANCE_S = 15.0
REPLAY_HIDDEN_MIN = 0.8  # A2 holds if the box is hidden in at least this share of replay shots
LIVE_HIDDEN_MAX = 0.2  # ... and in at most this share of live shots
GOAL_RECALL_MIN = 0.8  # A3 holds if at least this share of goals have a nearby peak
CHANCE_MARGIN_MIN = 0.2  # ... and that share beats chance by at least this much
BOX_PAD_PX = 6


def parse_clock(text: str) -> int | None:
    """Clock value in seconds found in ``text``, if any."""
    m = _CLOCK_RE.search(text)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


# ---------------------------------------------------------------------------
# A1: clock
# ---------------------------------------------------------------------------


@dataclass
class _Hit:
    half: int
    time_s: float
    rect: Rect
    clock_s: int


@dataclass
class ClockCheck:
    found: bool
    presence: float = 0.0
    linearity: float = 0.0
    box: Rect | None = None
    samples: int = 0


def _median_rect(hits: Sequence[_Hit]) -> Rect:
    return tuple(int(statistics.median(h.rect[i] for h in hits)) for i in range(4))  # type: ignore[return-value]


def _same_place(rect: Rect, centre: Rect) -> bool:
    x, y, w, h = rect
    cx, cy, cw, ch = centre
    dx = abs((x + w / 2) - (cx + cw / 2))
    dy = abs((y + h / 2) - (cy + ch / 2))
    return dx <= 0.5 * max(w, cw) and dy <= 0.5 * max(h, ch)


def _cluster(hits: Sequence[_Hit]) -> list[list[_Hit]]:
    clusters: list[list[_Hit]] = []
    for hit in hits:
        target = next((c for c in clusters if _same_place(hit.rect, _median_rect(c))), None)
        if target is None:
            clusters.append([hit])
        else:
            target.append(hit)
    return clusters


def linearity(hits: Sequence[_Hit], cfg: ScoreboardConfig) -> float:
    """Share of consecutive same-half samples whose clock advances with the video."""
    ordered = sorted(hits, key=lambda h: (h.half, h.time_s))
    passed = total = 0
    for a, b in zip(ordered, ordered[1:]):
        if a.half != b.half or b.time_s <= a.time_s:
            continue
        total += 1
        rate = (b.clock_s - a.clock_s) / (b.time_s - a.time_s)
        passed += cfg.clock_rate_min <= rate <= cfg.clock_rate_max
    return passed / total if total else 0.0


def measure_clock(
    points: Sequence[tuple[int, float]],
    read_frame: FrameReader,
    ocr: TextReader,
    cfg: ScoreboardConfig,
) -> ClockCheck:
    """Find the screen position that best behaves like a running match clock."""
    hits: list[_Hit] = []
    read = 0
    for half, t in points:
        frame = read_frame(half, t)
        if frame is None:
            continue
        read += 1
        for item in ocr(frame):
            clock = parse_clock(item.text)
            if clock is not None:
                hits.append(_Hit(half, t, item.rect, clock))
    if read == 0:
        return ClockCheck(found=False)

    best: ClockCheck | None = None
    for cluster in _cluster(hits):
        presence = len({(h.half, h.time_s) for h in cluster}) / read
        line = linearity(cluster, cfg)
        found = presence >= cfg.min_valid_ratio and line >= cfg.clock_linear_ratio
        candidate = ClockCheck(found, presence, line, _median_rect(cluster), read)
        if (
            best is None
            or (candidate.found, candidate.presence) > (best.found, best.presence)
        ):
            best = candidate
    return best or ClockCheck(found=False, samples=read)


# ---------------------------------------------------------------------------
# A2: replays
# ---------------------------------------------------------------------------


@dataclass
class ReplayCheck:
    replay_hidden: float | None = None
    live_hidden: float | None = None
    replay_shots: int = 0
    live_shots: int = 0


def shot_midpoints(
    cameras: Sequence[CameraLabel], durations: dict[int, float]
) -> list[tuple[int, float, bool]]:
    """(half, mid-shot time, is_replay) for each camera shot; a shot ends at the next label."""
    out: list[tuple[int, float, bool]] = []
    for half in sorted({c.half for c in cameras}):
        rows = sorted((c for c in cameras if c.half == half), key=lambda c: c.position_ms)
        for i, cam in enumerate(rows):
            start = cam.position_ms / 1000
            end = rows[i + 1].position_ms / 1000 if i + 1 < len(rows) else durations.get(half, 0.0)
            if end > start:
                out.append((half, (start + end) / 2, cam.replay))
    return out


def _evenly(items: Sequence, limit: int) -> list:
    if len(items) <= limit:
        return list(items)
    return [items[i] for i in np.linspace(0, len(items) - 1, limit).astype(int)]


def _box_visible(frame: np.ndarray, box: Rect, ocr: TextReader) -> bool:
    x, y, w, h = box
    x0, y0 = max(0, x - BOX_PAD_PX), max(0, y - BOX_PAD_PX)
    crop = frame[y0 : y + h + BOX_PAD_PX, x0 : x + w + BOX_PAD_PX]
    if crop.size == 0:
        return False
    # OCR on a tight crop often splits a clock ("45:0", "3"), so any digits count as visible.
    return sum(ch.isdigit() for item in ocr(crop) for ch in item.text) >= 2


def _hidden_share(
    shots: Sequence[tuple[int, float, bool]],
    read_frame: FrameReader,
    box: Rect,
    ocr: TextReader,
) -> tuple[float | None, int]:
    hidden = total = 0
    for half, t, _ in shots:
        frame = read_frame(half, t)
        if frame is None:
            continue
        total += 1
        hidden += not _box_visible(frame, box, ocr)
    return (hidden / total if total else None), total


def measure_replays(
    shots: Sequence[tuple[int, float, bool]],
    read_frame: FrameReader,
    box: Rect,
    ocr: TextReader,
    max_per_class: int = 40,
) -> ReplayCheck:
    """How often the located box is hidden during replay shots versus live shots."""
    replay = _evenly([s for s in shots if s[2]], max_per_class)
    live = _evenly([s for s in shots if not s[2]], max_per_class)
    replay_hidden, n_replay = _hidden_share(replay, read_frame, box, ocr)
    live_hidden, n_live = _hidden_share(live, read_frame, box, ocr)
    return ReplayCheck(replay_hidden, live_hidden, n_replay, n_live)


# ---------------------------------------------------------------------------
# A3: audio
# ---------------------------------------------------------------------------


@dataclass
class AudioCheck:
    goals: int = 0
    goals_near_peak: int = 0
    shots: int = 0
    shots_near_peak: int = 0
    peaks_per_min: float | None = None
    chance_level: float | None = None

    @property
    def goal_recall(self) -> float | None:
        return self.goals_near_peak / self.goals if self.goals else None

    @property
    def shot_recall(self) -> float | None:
        return self.shots_near_peak / self.shots if self.shots else None


def excitement_peaks(values: Sequence[float], cfg: MomentsConfig) -> np.ndarray:
    """Peak times in seconds: smoothed local maxima, using the rules in ARCHITECTURE.md."""
    if not len(values):
        return np.array([], dtype=int)
    width = max(1, int(cfg.peak_smooth_s))
    smooth = np.convolve(np.asarray(values, float), np.ones(width) / width, mode="same")
    peaks, _ = find_peaks(
        smooth, prominence=cfg.peak_prominence, distance=max(1, int(cfg.peak_min_gap_s))
    )
    return peaks


def measure_audio(
    excitement: dict[int, Sequence[float]],
    labels: Sequence[Label],
    cfg: MomentsConfig,
    tolerance_s: float = PEAK_TOLERANCE_S,
) -> AudioCheck:
    """How often goals and shots on target have an excitement peak within the tolerance."""
    result = AudioCheck()
    peaks_total = 0
    in_play_s = covered_s = 0.0

    for half, values in excitement.items():
        peaks = excitement_peaks(values, cfg)
        half_labels = [lab for lab in labels if lab.half == half]
        times = [lab.position_ms / 1000 for lab in half_labels]
        start, end = (min(times), max(times)) if times else (0.0, float(len(values)))
        in_window = peaks[(peaks >= start) & (peaks <= end)]
        peaks_total += len(in_window)
        in_play_s += max(0.0, end - start)
        seconds = np.arange(int(start), int(end) + 1)
        if len(seconds) and len(peaks):
            covered_s += float((np.abs(seconds[:, None] - peaks).min(axis=1) <= tolerance_s).sum())

        for lab in half_labels:
            t = lab.position_ms / 1000
            near = bool(len(peaks)) and float(np.abs(peaks - t).min()) <= tolerance_s
            if lab.label == "Goal":
                result.goals += 1
                result.goals_near_peak += near
            elif lab.label == "Shots on target":
                result.shots += 1
                result.shots_near_peak += near

    if in_play_s > 0:
        result.peaks_per_min = peaks_total / (in_play_s / 60)
        result.chance_level = min(1.0, covered_s / in_play_s)
    return result


# ---------------------------------------------------------------------------
# Commentary language
# ---------------------------------------------------------------------------


class LanguageDetector(Protocol):
    def detect(self, wav: Path) -> str: ...


class WhisperLanguageDetector:
    """Language of an audio window, using faster-whisper on the CPU."""

    def __init__(self, model_name: str, compute_type: str, models_dir: Path) -> None:
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            model_name, device="cpu", compute_type=compute_type, download_root=str(models_dir)
        )

    def detect(self, wav: Path) -> str:
        _, info = self._model.transcribe(str(wav), beam_size=1)
        return info.language


def _audio_window(video: Path, start_s: float, seconds: float, out: Path) -> None:
    subprocess.run(
        [
            find_binary("ffmpeg"),
            "-y",
            "-v",
            "error",
            "-ss",
            f"{start_s:.2f}",
            "-i",
            str(video),
            "-t",
            f"{seconds:.2f}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(out),
        ],
        check=True,
    )


def detect_language(
    halves: Sequence[tuple[Path, float]], detector: LanguageDetector, windows: int
) -> str:
    """Most common language across windows spread over both halves."""
    votes: Counter[str] = Counter()
    spots = [(video, duration, f) for video, duration in halves for f in (0.25, 0.5, 0.75)]
    with tempfile.TemporaryDirectory() as tmp:
        for i, (video, duration, fraction) in enumerate(_evenly(spots, windows)):
            wav = Path(tmp) / f"w{i}.wav"
            _audio_window(video, duration * fraction, 30.0, wav)
            votes[detector.detect(wav)] += 1
    return votes.most_common(1)[0][0] if votes else "unknown"


# ---------------------------------------------------------------------------
# Whole-match run
# ---------------------------------------------------------------------------


@dataclass
class MatchResult:
    game: str
    clock: ClockCheck
    replays: ReplayCheck = field(default_factory=ReplayCheck)
    audio: AudioCheck = field(default_factory=AudioCheck)
    language: str = "unknown"


def load_games(path: Path) -> list[str]:
    """Game folders from a manifest; only ``game`` is required for this check."""
    raw = yaml.safe_load(path.read_text())
    items = raw.get("matches", []) if isinstance(raw, dict) else raw
    games = []
    for i, item in enumerate(items or []):
        game = item if isinstance(item, str) else (item or {}).get("game")
        if not game:
            raise ValueError(f"Manifest entry #{i} has no 'game'")
        games.append(str(game))
    return games


def sample_points(durations: dict[int, float], total: int) -> list[tuple[int, float]]:
    """``total`` evenly spaced (half, time) points, shared equally between the halves."""
    per_half = max(1, total // max(1, len(durations)))
    return [
        (half, round((i + 0.5) * duration / per_half, 3))
        for half, duration in sorted(durations.items())
        for i in range(per_half)
    ]


def check_match(
    game: str,
    videos: Path,
    labels_root: Path,
    cfg: ReelConfig,
    ocr: TextReader,
    tagger: Tagger | None,
    detector: LanguageDetector | None,
    sample_frames: int | None = None,
    max_shots_per_class: int = 40,
) -> MatchResult:
    half1, half2 = find_half_files(game, videos)
    files = {1: half1, 2: half2}
    metas = {half: probe_video(path) for half, path in files.items()}
    durations = {half: meta.duration_s for half, meta in metas.items()}

    labels_dir = labels_root / game
    names = ("Labels-v2.json", "Labels-cameras.json")
    missing = [name for name in names if not (labels_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"{game}: missing {', '.join(missing)} under {labels_dir}")
    labels = load_labels(labels_dir / "Labels-v2.json")
    cameras = load_camera_labels(labels_dir / "Labels-cameras.json")

    def read_frame(half: int, t: float) -> np.ndarray | None:
        meta = metas[half]
        return grab_frame(files[half], t, meta.width, meta.height)

    frames = sample_frames if sample_frames is not None else cfg.scoreboard.sample_frames
    clock = measure_clock(sample_points(durations, frames), read_frame, ocr, cfg.scoreboard)
    result = MatchResult(game=game, clock=clock)

    if clock.box is not None:
        result.replays = measure_replays(
            shot_midpoints(cameras, durations), read_frame, clock.box, ocr, max_shots_per_class
        )

    excitement = _match_excitement(files, durations, cfg.audio, tagger)
    result.audio = measure_audio(excitement, labels, cfg.moments)

    if detector is not None:
        halves = [(files[h], durations[h]) for h in sorted(files)]
        result.language = detect_language(halves, detector, cfg.commentary.language_check_windows)
    return result


def _match_excitement(
    files: dict[int, Path],
    durations: dict[int, float],
    cfg: AudioConfig,
    tagger: Tagger | None,
) -> dict[int, list[float]]:
    out: dict[int, list[float]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for half, video in files.items():
            wav = Path(tmp) / f"half{half}.wav"
            extract_audio(video, wav)
            rows = compute_excitement(wav, durations[half], cfg, tagger)
            out[half] = [row["excitement"] for row in rows]
            wav.unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _avg(values: Sequence[float | None]) -> float | None:
    known = [v for v in values if v is not None]
    return sum(known) / len(known) if known else None


def recommend(results: Sequence[MatchResult]) -> dict[str, str]:
    """One recommendation per assumption: holds, or what to change."""
    found = sum(r.clock.found for r in results)
    a1 = (
        f"Holds: clock found on {found} of {len(results)} matches."
        if results and found >= 0.9 * len(results)
        else f"Check needed: clock found on only {found} of {len(results)} matches. "
        "Review the failing broadcasts and consider score-based detection as a second route."
    )

    replay, live = _avg([r.replays.replay_hidden for r in results]), _avg(
        [r.replays.live_hidden for r in results]
    )
    if replay is None or live is None:
        a2 = "Not measured: no match had both replay and live shots with a located box."
    elif replay >= REPLAY_HIDDEN_MIN and live <= LIVE_HIDDEN_MAX:
        a2 = f"Holds: box hidden in {replay:.0%} of replay shots and {live:.0%} of live shots."
    else:
        a2 = (
            f"Does not hold: box hidden in {replay:.0%} of replay shots and {live:.0%} of live "
            "shots. Change replay detection in slice 44, for example to transition detection."
        )

    goals = sum(r.audio.goals for r in results)
    near = sum(r.audio.goals_near_peak for r in results)
    chance = _avg([r.audio.chance_level for r in results])
    if not goals or chance is None:
        a3 = "Not measured: no goals with audio."
    elif near / goals >= GOAL_RECALL_MIN and near / goals - chance >= CHANCE_MARGIN_MIN:
        a3 = f"Holds: {near / goals:.0%} of goals have a peak nearby (chance level {chance:.0%})."
    else:
        a3 = (
            f"Does not hold: {near / goals:.0%} of goals have a peak nearby (chance level "
            f"{chance:.0%}). Tune or change excitement in slice 43."
        )
    return {"A1 clock": a1, "A2 replays": a2, "A3 audio": a3}


def _short_name(game: str) -> str:
    return game.rstrip("/").split("/")[-1]


def report_markdown(results: Sequence[MatchResult]) -> str:
    lines = [
        "# Real-match assumption check",
        "",
        f"{len(results)} match(es). Numbers only: no frames or broadcast text.",
        "",
        "## Recommendation",
        "",
    ]
    lines += [f"- **{name}:** {text}" for name, text in recommend(results).items()]
    lines += [
        "",
        "## A1: clock",
        "",
        "| Match | Found | Presence | Linearity | Frames read |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        c = r.clock
        lines.append(
            f"| {_short_name(r.game)} | {'yes' if c.found else 'no'} | {_pct(c.presence)} "
            f"| {_pct(c.linearity)} | {c.samples} |"
        )
    lines += [
        "",
        "## A2: score graphic during replays",
        "",
        "| Match | Hidden in replay shots | Hidden in live shots | Replay shots | Live shots |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        p = r.replays
        lines.append(
            f"| {_short_name(r.game)} | {_pct(p.replay_hidden)} | {_pct(p.live_hidden)} "
            f"| {p.replay_shots} | {p.live_shots} |"
        )
    lines += [
        "",
        f"## A3: excitement peaks within ±{PEAK_TOLERANCE_S:.0f} s",
        "",
        "| Match | Goals with peak | Shots on target with peak | Peaks per minute | Chance level |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        a = r.audio
        rate = "n/a" if a.peaks_per_min is None else f"{a.peaks_per_min:.2f}"
        lines.append(
            f"| {_short_name(r.game)} | {a.goals_near_peak}/{a.goals} ({_pct(a.goal_recall)}) "
            f"| {a.shots_near_peak}/{a.shots} ({_pct(a.shot_recall)}) | {rate} "
            f"| {_pct(a.chance_level)} |"
        )
    lines += ["", "## Commentary language", "", "| Match | Language |", "|---|---|"]
    lines += [f"| {_short_name(r.game)} | {r.language} |" for r in results]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check design assumptions on real matches")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--videos", type=Path, default=Path("data/soccernet/videos-720p"))
    parser.add_argument("--labels", type=Path, default=EVAL_DIR / "soccernet")
    parser.add_argument("--out", type=Path, default=REPORT_PATH)
    parser.add_argument("--no-panns", action="store_true", help="use loudness only (much faster)")
    parser.add_argument("--no-language", action="store_true", help="skip the language check")
    args = parser.parse_args(argv)

    cfg = load_config()
    models_dir = Path(cfg.models_dir)
    tagger = None if args.no_panns else PannsTagger(models_dir)
    detector = (
        None
        if args.no_language
        else WhisperLanguageDetector(
            cfg.commentary.whisper_model, cfg.commentary.compute_type, models_dir
        )
    )
    results = [
        check_match(game, args.videos, args.labels, cfg, read_text, tagger, detector)
        for game in load_games(args.manifest)
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report_markdown(results))
    print(f"Report written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
