"""Synthetic football broadcast generator for testing Reel without real footage.

Builds a scripted fake match with ffmpeg and writes a ground-truth ``schedule.json``:

- solid-colour scenes, one per ``ShotLabel``, separated by hard cuts;
- a score graphic at a fixed position with a ticking clock, in a configurable style
  (``ARS 1-0 CHE``, ``ARS 1 0 CHE``, ``ARS 1:0 CHE``);
- goals whose score updates a known lag after the goal;
- replays with the graphic hidden, one overturned goal, and a half-time break with no
  graphic and a clock restart;
- audio: background noise with bursts at known times, including one with no goal.

Usage::

    uv run python -m tests.fixtures.make_football --out ./data/synthetic-football
"""

from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from reel.ingest.probe import find_binary

VIDEO_NAME = "video.mp4"
SCHEDULE_NAME = "schedule.json"
FONT = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "Inter-Bold.ttf"

SCENE_COLOURS: dict[str, str] = {
    "wide": "0x2E7D32",
    "medium": "0x558B2F",
    "close_up": "0x8D6E63",
    "crowd": "0x5C6BC0",
    "graphic": "0x263238",
}
STYLES: dict[str, str] = {"dash": "{h}-{a}", "space": "{h} {a}", "colon": "{h}:{a}"}
HOME, AWAY = "ARS", "CHE"

MIN_DURATION_S = 150.0
PRE_MATCH_S = 8.0  # graphic-only opening, no score box
BREAK_S = 14.0  # half-time, no score box
SCORE_LAG_S = 10.0  # the score updates this long after the goal
OVERTURN_DELAY_S = 12.0  # an overturned goal is removed this long after it appears
REPLAY_GAP_S = 2.0  # a replay starts this long after the score update
REPLAY_S = 4.0
BURST_S = 3.0
FIRST_HALF_CLOCK_S = 1800  # 30:00, so captions in tests have realistic minutes
SECOND_HALF_CLOCK_S = 2700  # 45:00; pass 0 for broadcasts that restart at 00:00
MIN_SHOT_S = 1.0


def _text(style: str, home: int, away: int) -> str:
    return f"{HOME} {STYLES[style].format(h=home, a=away)} {AWAY}"


def _fill_shots(
    start: float, end: float, forced: list[dict[str, Any]], rng: random.Random
) -> list[dict[str, Any]]:
    """Cover [start, end) with the forced shots, alternating wide and medium in the gaps."""
    shots: list[dict[str, Any]] = []

    def fill_gap(a: float, b: float) -> None:
        t, scene = a, "wide"
        while b - t > 1e-6:
            length = (9.0 if scene == "wide" else 4.0) + rng.uniform(-1.0, 1.0)
            stop = t + length if b - (t + length) >= MIN_SHOT_S else b
            shots.append(
                {"start_s": round(t, 2), "end_s": round(stop, 2), "scene": scene, "replay": False}
            )
            t, scene = stop, "medium" if scene == "wide" else "wide"

    cursor = start
    for shot in sorted(forced, key=lambda s: s["start_s"]):
        if shot["start_s"] > cursor:
            fill_gap(cursor, shot["start_s"])
        shots.append(shot)
        cursor = shot["end_s"]
    if end > cursor:
        fill_gap(cursor, end)
    return shots


def build_schedule(
    duration_s: float = 180.0,
    width: int = 1280,
    height: int = 720,
    fps: int = 25,
    has_audio: bool = True,
    style: str = "dash",
    second_half_clock_s: int = SECOND_HALF_CLOCK_S,
    seed: int = 42,
) -> dict[str, Any]:
    """Build the ground-truth schedule for a synthetic football match (no rendering)."""
    if style not in STYLES:
        raise ValueError(f"Unknown graphic style: {style!r}")
    if duration_s < MIN_DURATION_S:
        raise ValueError(f"duration_s must be at least {MIN_DURATION_S}")

    rng = random.Random(seed)
    in_play = duration_s - PRE_MATCH_S - BREAK_S
    h1_start, h1_end = PRE_MATCH_S, round(PRE_MATCH_S + in_play * 0.46, 2)
    h2_start, h2_end = round(h1_end + BREAK_S, 2), float(duration_s)
    l1, l2 = h1_end - h1_start, h2_end - h2_start

    plan = [
        {"side": "home", "t": h1_start + 0.25 * l1, "half": 1, "overturn": False, "replay": True},
        {"side": "away", "t": h2_start + 0.05 * l2, "half": 2, "overturn": False, "replay": True},
        {"side": "home", "t": h2_start + 0.45 * l2, "half": 2, "overturn": True, "replay": False},
        {"side": "home", "t": h2_start + 0.85 * l2, "half": 2, "overturn": False, "replay": False},
    ]
    chance_t = round(h1_start + 0.75 * l1, 2)

    home, away = 0, 0
    changes = [
        {
            "time_s": 0.0,
            "event": "initial",
            "home": 0,
            "away": 0,
            "text": _text(style, 0, 0),
        }
    ]
    goals: list[dict[str, Any]] = []
    bursts = [{"start_s": chance_t, "end_s": round(chance_t + BURST_S, 2), "kind": "chance"}]
    replays: list[list[float]] = []
    forced = {1: [], 2: []}  # type: dict[int, list[dict[str, Any]]]

    def add_forced(half: int, a: float, b: float, scene: str, replay: bool = False) -> None:
        forced[half].append(
            {"start_s": round(a, 2), "end_s": round(b, 2), "scene": scene, "replay": replay}
        )

    add_forced(1, chance_t + 2.0, chance_t + 4.0, "close_up")

    for item in plan:
        t = round(item["t"], 2)
        update = round(t + SCORE_LAG_S, 2)
        half = item["half"]
        if item["side"] == "home":
            home += 1
        else:
            away += 1
        changes.append(
            {
                "time_s": update,
                "event": "goal",
                "home": home,
                "away": away,
                "text": _text(style, home, away),
            }
        )
        goal = {
            "side": item["side"],
            "half": half,
            "t_goal_s": t,
            "t_update_s": update,
            "overturned": item["overturn"],
            "t_overturn_s": None,
        }
        bursts.append({"start_s": t, "end_s": round(t + BURST_S, 2), "kind": "goal"})
        add_forced(half, t + 2.0, t + 5.0, "close_up")
        add_forced(half, t + 5.0, t + 8.0, "crowd")
        if item["replay"]:
            r0, r1 = round(update + REPLAY_GAP_S, 2), round(update + REPLAY_GAP_S + REPLAY_S, 2)
            replays.append([r0, r1])
            add_forced(half, r0, r1, "wide", replay=True)
        if item["overturn"]:
            removed = round(update + OVERTURN_DELAY_S, 2)
            goal["t_overturn_s"] = removed
            home -= 1
            changes.append(
                {
                    "time_s": removed,
                    "event": "goal_overturned",
                    "home": home,
                    "away": away,
                    "text": _text(style, home, away),
                }
            )
        goals.append(goal)

    changes.sort(key=lambda c: c["time_s"])
    bursts.sort(key=lambda b: b["start_s"])

    def graphic(a: float, b: float) -> dict[str, Any]:
        return {"start_s": a, "end_s": b, "scene": "graphic", "replay": False}

    shots = [
        graphic(0.0, h1_start),
        *_fill_shots(h1_start, h1_end, forced[1], rng),
        graphic(h1_end, h2_start),
        *_fill_shots(h2_start, h2_end, forced[2], rng),
    ]

    hidden = sorted([[0.0, h1_start], [h1_end, h2_start], *replays])
    bw, bh = round(width * 0.36), round(height * 0.075)
    box = [round(width * 0.04), round(height * 0.05), bw, bh]
    clock_w = round(bw * 0.3)
    return {
        "duration_s": float(duration_s),
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": has_audio,
        "style": style,
        "seed": seed,
        "teams": [HOME, AWAY],
        "scorebox_rect": box,
        "clock_rect": [box[0] + bw - clock_w, box[1], clock_w, bh],
        "halves": [
            {"half": 1, "start_s": h1_start, "end_s": h1_end, "clock_start_s": FIRST_HALF_CLOCK_S},
            {"half": 2, "start_s": h2_start, "end_s": h2_end, "clock_start_s": second_half_clock_s},
        ],
        "shots": shots,
        "cuts": [s["start_s"] for s in shots[1:]],
        "scenes": [s["scene"] for s in shots],
        "goals": goals,
        "score_changes": changes,
        "replays": replays,
        "hidden_intervals": hidden,
        "bursts": bursts if has_audio else [],
        "final_score": _text(style, home, away),
    }


def _hidden_at(schedule: dict[str, Any], t: float) -> bool:
    return any(h0 <= t < h1 for h0, h1 in schedule["hidden_intervals"])


def score_text_at(schedule: dict[str, Any], t: float) -> str | None:
    """Score text visible at time ``t`` (None while the graphic is hidden)."""
    if _hidden_at(schedule, t):
        return None
    text = None
    for change in schedule["score_changes"]:
        if change["time_s"] <= t:
            text = change["text"]
    return text


def clock_seconds_at(schedule: dict[str, Any], t: float) -> int | None:
    """Match clock in seconds at time ``t`` (None outside the halves)."""
    for half in schedule["halves"]:
        if half["start_s"] <= t < half["end_s"]:
            return math.floor(t - half["start_s"] + half["clock_start_s"])
    return None


def clock_text_at(schedule: dict[str, Any], t: float) -> str | None:
    """Clock text visible at time ``t`` (None while the graphic is hidden)."""
    seconds = clock_seconds_at(schedule, t)
    if seconds is None or _hidden_at(schedule, t):
        return None
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _between(a: float, b: float) -> str:
    return f"between(t\\,{a:.2f}\\,{b - 0.001:.3f})"


def _escape(path: Path) -> str:
    """Escape a path for use inside an ffmpeg filter argument."""
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _video_filters(schedule: dict[str, Any], text_dir: Path) -> str:
    """Build the video filter chain; drawtext strings go in files under ``text_dir``."""
    w, h = schedule["width"], schedule["height"]
    font = _escape(FONT)

    def text_file(name: str, content: str) -> str:
        path = text_dir / name
        path.write_text(content)
        return _escape(path)

    filters: list[str] = []
    for shot in schedule["shots"]:
        en = _between(shot["start_s"], shot["end_s"])
        colour = SCENE_COLOURS[shot["scene"]]
        filters.append(f"drawbox=x=0:y=0:w={w}:h={h}:color={colour}:t=fill:enable='{en}'")

    x, y, bw, bh = schedule["scorebox_rect"]
    cx, _, _, _ = schedule["clock_rect"]
    visible = "*".join(f"not({_between(h0, h1)})" for h0, h1 in schedule["hidden_intervals"])
    size = int(bh * 0.6)
    filters.append(f"drawbox=x={x}:y={y}:w={bw}:h={bh}:color=0x0D1B2A:t=fill:enable='{visible}'")

    changes = schedule["score_changes"]
    end_of_video = schedule["duration_s"] + 1
    for i, change in enumerate(changes):
        until = changes[i + 1]["time_s"] if i + 1 < len(changes) else end_of_video
        en = f"{_between(change['time_s'], until)}*{visible}"
        source = text_file(f"score_{i}.txt", change["text"])
        filters.append(
            f"drawtext=fontfile='{font}':textfile='{source}':fontcolor=white"
            f":fontsize={size}:x={x + int(bh * 0.3)}:y={y}+({bh}-th)/2:enable='{en}'"
        )

    for half in schedule["halves"]:
        seconds = f"floor(t-{half['start_s']:.2f}+{half['clock_start_s']})"
        text = f"%{{eif:floor({seconds}/60):d:2}}:%{{eif:mod({seconds},60):d:2}}"
        en = f"{_between(half['start_s'], half['end_s'])}*{visible}"
        source = text_file(f"clock_{half['half']}.txt", text)
        filters.append(
            f"drawtext=fontfile='{font}':textfile='{source}':fontcolor=white"
            f":fontsize={size}:x={cx}:y={y}+({bh}-th)/2:enable='{en}'"
        )
    return ",".join(filters)


def _audio_filter(schedule: dict[str, Any]) -> str:
    loud = "+".join(_between(b["start_s"], b["end_s"]) for b in schedule["bursts"]) or "0"
    return f"volume=eval=frame:volume='0.04+0.96*min(1\\,{loud})'"


def generate_football_video(
    output_dir: Path | str,
    duration_s: float = 180.0,
    has_audio: bool = True,
    width: int = 1280,
    height: int = 720,
    fps: int = 25,
    style: str = "dash",
    second_half_clock_s: int = SECOND_HALF_CLOCK_S,
    seed: int = 42,
) -> tuple[Path, Path]:
    """Render a synthetic football match and its schedule; returns (video, schedule)."""
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    video_path = out_dir / VIDEO_NAME
    schedule_path = out_dir / SCHEDULE_NAME

    schedule = build_schedule(
        duration_s=duration_s,
        width=width,
        height=height,
        fps=fps,
        has_audio=has_audio,
        style=style,
        second_half_clock_s=second_half_clock_s,
        seed=seed,
    )
    cmd = [
        find_binary("ffmpeg"),
        "-y",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={width}x{height}:r={fps}:d={duration_s}",
    ]
    if has_audio:
        noise = f"anoisesrc=color=pink:amplitude=0.6:seed={seed}:duration={duration_s}"
        cmd += ["-f", "lavfi", "-i", f"{noise}:sample_rate=44100"]
    if has_audio:
        cmd += ["-af", _audio_filter(schedule), "-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-an"]
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-t",
        str(duration_s),
        str(video_path),
    ]

    with tempfile.TemporaryDirectory(dir=out_dir) as tmp:
        filter_script = Path(tmp) / "video_filters.txt"
        filter_script.write_text(_video_filters(schedule, Path(tmp)))
        cmd[-1:-1] = ["-filter_script:v", str(filter_script)]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not video_path.is_file():
        raise RuntimeError(f"Synthetic football video generation failed: {proc.stderr}")

    schedule_path.write_text(json.dumps(schedule, indent=2))
    return video_path, schedule_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a synthetic football match video")
    parser.add_argument("--out", default="./data/synthetic-football")
    parser.add_argument("--duration", type=float, default=180.0)
    parser.add_argument("--style", choices=sorted(STYLES), default="dash")
    parser.add_argument("--second-half-clock", type=int, default=SECOND_HALF_CLOCK_S)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-audio", action="store_true")
    args = parser.parse_args(argv)

    video, schedule = generate_football_video(
        output_dir=args.out,
        duration_s=args.duration,
        has_audio=not args.no_audio,
        style=args.style,
        second_half_clock_s=args.second_half_clock,
        seed=args.seed,
    )
    print(f"Generated synthetic football video: {video}")
    print(f"Generated schedule: {schedule}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
