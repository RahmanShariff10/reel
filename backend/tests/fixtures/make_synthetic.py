"""Synthetic cricket broadcast generator for testing Reel without real footage.

Builds a scripted fake "match" with ffmpeg and writes a ground-truth
``schedule.json`` next to it:

- solid-colour scenes separated by hard cuts (``run_up`` = green field with a
  brown pitch rectangle; ``field``, ``close_up``, ``crowd``, ``graphic``);
- a score box drawn at a fixed position whose text changes after every
  delivery, covering fours, sixes, wickets, one DRS reversal and one innings
  reset;
- "replay" shots (run-up scene with the score box hidden) after big moments;
- audio: quiet background noise with loud bursts after big moments.

Usage::

    uv run python -m tests.fixtures.make_synthetic --out ./data/synthetic
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reel.ingest.probe import find_binary

VIDEO_NAME = "video.mp4"
SCHEDULE_NAME = "schedule.json"

# Scene colours (ffmpeg colour names / hex)
SCENE_COLOURS: dict[str, str] = {
    "run_up": "0x2E7D32",  # green field (pitch rectangle drawn on top)
    "field": "0x66BB6A",
    "close_up": "0x8D6E63",
    "crowd": "0x5C6BC0",
    "graphic": "0x263238",
}
PITCH_COLOUR = "0xC2A878"

# Scripted outcomes per delivery. Kept fixed so every duration >= ~100 s covers
# fours, sixes, wickets, a DRS reversal and an innings reset.
OUTCOMES: list[str] = [
    "single", "four", "dot", "wicket", "six", "wicket_drs", "single", "innings_break",
    "four", "six", "dot", "wicket", "single", "four", "six",
]
BIG = {"four", "six", "wicket", "wicket_drs"}

# Shot durations in seconds
RUN_UP_S = 4.0
FIELD_S = 4.0
REPLAY_S = 3.0
REACTION_S = 2.5
GRAPHIC_S = 4.0
SCORE_LAG_S = 2.0  # score box updates this long after the run-up shot ends
BURST_S = 3.0  # crowd burst length after a big moment
DRS_DELAY_S = 9.0  # wicket reversed this long after the wicket is shown

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def find_font() -> str:
    """Return a TrueType font usable by ffmpeg drawtext."""
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise FileNotFoundError(
        "No usable TrueType font found for drawtext; install DejaVu Sans or Arial."
    )


@dataclass
class _State:
    team: str
    runs: int
    wickets: int
    balls: int  # legal balls bowled in the innings
    innings: int

    @property
    def overs(self) -> str:
        return f"{self.balls // 6}.{self.balls % 6}"


def _score_text(state: _State, order: str) -> str:
    pair = (
        f"{state.runs}/{state.wickets}"
        if order == "runs-wickets"
        else f"{state.wickets}/{state.runs}"
    )
    return f"{state.team} {pair}  {state.overs}"


def build_schedule(
    duration_s: float = 120.0,
    width: int = 1280,
    height: int = 720,
    fps: int = 25,
    has_audio: bool = True,
    order: str = "runs-wickets",
    scorebox: bool = True,
    distractor: bool = False,
    seed: int = 42,
) -> dict[str, Any]:
    """Build the ground-truth schedule for a synthetic match (no rendering)."""
    rng = random.Random(seed)
    jitter = lambda: round(rng.uniform(-0.3, 0.3), 2)  # noqa: E731

    state = _State(team="IND", runs=100 + rng.randint(0, 40), wickets=2, balls=90, innings=1)
    shots: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    hidden: list[list[float]] = []
    bursts: list[list[float]] = []
    deliveries: list[dict[str, Any]] = []

    def add_shot(scene: str, length: float, replay: bool = False) -> float:
        start = shots[-1]["end_s"] if shots else 0.0
        end = round(start + length, 2)
        shots.append({"start_s": round(start, 2), "end_s": end, "scene": scene, "replay": replay})
        return end

    def add_change(t: float, event: str, runs_delta: int = 0, wicket_delta: int = 0) -> None:
        changes.append({
            "time_s": round(t, 2),
            "event": event,
            "text": _score_text(state, order),
            "team": state.team,
            "runs": state.runs,
            "wickets": state.wickets,
            "overs": state.overs,
            "innings": state.innings,
            "runs_delta": runs_delta,
            "wicket_delta": wicket_delta,
        })

    # Initial score shown from t=0
    add_change(0.0, "initial")

    for outcome in OUTCOMES:
        if outcome == "innings_break":
            start = shots[-1]["end_s"] if shots else 0.0
            end = add_shot("graphic", GRAPHIC_S)
            if end > duration_s:
                shots.pop()
                break
            hidden.append([start, end])
            state = _State(team="AUS", runs=0, wickets=0, balls=0, innings=2)
            add_change(end, "innings_start")
            continue

        # Need room for a full delivery unit
        unit = RUN_UP_S + FIELD_S + REACTION_S + (REPLAY_S if outcome in BIG else 0)
        start = shots[-1]["end_s"] if shots else 0.0
        if start + unit > duration_s:
            break

        run_up_end = add_shot("run_up", RUN_UP_S + jitter())
        t_change = run_up_end + SCORE_LAG_S
        add_shot("field", FIELD_S)

        state.balls += 1
        runs_delta = {"single": 1, "four": 4, "six": 6}.get(outcome, 0)
        wicket_delta = 1 if outcome in ("wicket", "wicket_drs") else 0
        state.runs += runs_delta
        state.wickets += wicket_delta
        event = {"single": "runs", "dot": "dot", "four": "four", "six": "six"}.get(
            outcome, "wicket"
        )
        add_change(t_change, event, runs_delta, wicket_delta)

        replays = 0
        if outcome in BIG:
            bursts.append([round(run_up_end + 0.5, 2), round(run_up_end + 0.5 + BURST_S, 2)])
            r_start = shots[-1]["end_s"]
            r_end = add_shot("run_up", REPLAY_S, replay=True)
            hidden.append([r_start, r_end])
            replays = 1
        reaction_scene = "crowd" if outcome in BIG else "close_up"
        add_shot(reaction_scene, REACTION_S)

        deliveries.append({
            "start_s": shots[-(3 + replays)]["start_s"],
            "t_hit_s": round(run_up_end, 2),
            "outcome": outcome,
            "innings": state.innings,
            "over_ball": state.overs,
            "replay_count": replays,
        })

        if outcome == "wicket_drs":
            t_rev = t_change + DRS_DELAY_S
            # Only schedule the reversal if it lands while the box is visible
            state.wickets -= 1
            add_change(t_rev, "wicket_overturned", 0, -1)

    # Fill the remainder with a field shot so the video has no gap
    final_start = shots[-1]["end_s"] if shots else 0.0
    if final_start < duration_s:
        shots.append({"start_s": final_start, "end_s": round(duration_s, 2), "scene": "field",
                      "replay": False})
    shots[-1]["end_s"] = round(duration_s, 2)

    # Drop any changes scheduled past the end, and nudge reversals out of hidden spans
    for ch in changes:
        for h0, h1 in hidden:
            if h0 <= ch["time_s"] < h1 and ch["event"] == "wicket_overturned":
                ch["time_s"] = round(h1 + 0.5, 2)
    changes = [c for c in changes if c["time_s"] < duration_s]
    changes.sort(key=lambda c: c["time_s"])

    bw, bh = round(width * 0.30), round(height * 0.078)
    box = [round(width * 0.047), round(height * 0.875), bw, bh] if scorebox else None

    return {
        "duration_s": float(duration_s),
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": has_audio,
        "order": order,
        "seed": seed,
        "scorebox": scorebox,
        "distractor": distractor,
        "scorebox_rect": box,
        "distractor_rect": (
            [round(width * 0.80), round(height * 0.05), round(width * 0.15), bh]
            if distractor else None
        ),
        "distractor_text": "RR 8.25" if distractor else None,
        "shots": shots,
        "cuts": [s["start_s"] for s in shots[1:]],
        "scenes": [s["scene"] for s in shots],
        "score_changes": changes if scorebox else [],
        "hidden_intervals": hidden if scorebox else [],
        "deliveries": deliveries,
        "bursts": bursts if has_audio else [],
    }


def score_text_at(schedule: dict[str, Any], t: float) -> str | None:
    """Return the score text visible at time ``t`` (None if hidden or absent)."""
    if not schedule["scorebox"]:
        return None
    if any(h0 <= t < h1 for h0, h1 in schedule["hidden_intervals"]):
        return None
    text = None
    for ch in schedule["score_changes"]:
        if ch["time_s"] <= t:
            text = ch["text"]
    return text


def _between(a: float, b: float) -> str:
    return f"between(t\\,{a:.2f}\\,{b - 0.001:.3f})"


def _video_filters(schedule: dict[str, Any], font: str) -> str:
    w, h = schedule["width"], schedule["height"]
    filters: list[str] = []
    for shot in schedule["shots"]:
        scene = shot["scene"]
        en = _between(shot["start_s"], shot["end_s"])
        filters.append(
            f"drawbox=x=0:y=0:w={w}:h={h}:color={SCENE_COLOURS[scene]}:t=fill:enable='{en}'"
        )
        if scene == "run_up":
            filters.append(
                f"drawbox=x={int(w * 0.44)}:y={int(h * 0.25)}:w={int(w * 0.12)}:h={int(h * 0.6)}"
                f":color={PITCH_COLOUR}:t=fill:enable='{en}'"
            )

    if schedule["scorebox"]:
        x, y, bw, bh = schedule["scorebox_rect"]
        hidden = schedule["hidden_intervals"]
        visible = "*".join(f"not({_between(h0, h1)})" for h0, h1 in hidden) or "1"
        filters.append(
            f"drawbox=x={x}:y={y}:w={bw}:h={bh}:color=0x0D1B2A:t=fill:enable='{visible}'"
        )
        changes = schedule["score_changes"]
        dur = schedule["duration_s"]
        for i, ch in enumerate(changes):
            end = changes[i + 1]["time_s"] if i + 1 < len(changes) else dur + 1
            en = f"{_between(ch['time_s'], end)}*{visible}"
            filters.append(
                f"drawtext=fontfile='{font}':text='{ch['text']}':fontcolor=white"
                f":fontsize={int(bh * 0.6)}:x={x + int(bh * 0.3)}:y={y}+({bh}-th)/2"
                f":enable='{en}'"
            )

    if schedule["distractor"]:
        x, y, bw, bh = schedule["distractor_rect"]
        filters.append(f"drawbox=x={x}:y={y}:w={bw}:h={bh}:color=0x37474F:t=fill")
        filters.append(
            f"drawtext=fontfile='{font}':text='{schedule['distractor_text']}':fontcolor=white"
            f":fontsize={int(bh * 0.6)}:x={x + int(bh * 0.3)}:y={y}+({bh}-th)/2"
        )
    return ",".join(filters)


def _audio_filter(schedule: dict[str, Any]) -> str:
    bursts = schedule["bursts"]
    loud = "+".join(_between(b0, b1) for b0, b1 in bursts) or "0"
    return f"volume=eval=frame:volume='0.04+0.96*min(1\\,{loud})'"


def generate_synthetic_video(
    output_dir: Path | str,
    duration_s: float = 120.0,
    has_audio: bool = True,
    width: int = 1280,
    height: int = 720,
    fps: int = 25,
    order: str = "runs-wickets",
    distractor: bool = False,
    seed: int = 42,
    scorebox: bool = True,
) -> tuple[Path, Path]:
    """Render a synthetic match video and its ground-truth schedule.json.

    Returns ``(video_path, schedule_path)``.
    """
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    video_path = out_dir / VIDEO_NAME
    schedule_path = out_dir / SCHEDULE_NAME

    schedule = build_schedule(
        duration_s=duration_s, width=width, height=height, fps=fps, has_audio=has_audio,
        order=order, scorebox=scorebox, distractor=distractor, seed=seed,
    )
    ffmpeg = find_binary("ffmpeg")
    font = find_font()

    filter_script = out_dir / ".video_filters.txt"
    filter_script.write_text(_video_filters(schedule, font))

    cmd = [
        ffmpeg, "-y", "-v", "error",
        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={fps}:d={duration_s}",
    ]
    if has_audio:
        cmd += ["-f", "lavfi", "-i",
                f"anoisesrc=color=pink:amplitude=0.6:seed={seed}:duration={duration_s}"
                ":sample_rate=44100"]
    cmd += ["-filter_script:v", str(filter_script)]
    if has_audio:
        cmd += ["-af", _audio_filter(schedule), "-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-t", str(duration_s), str(video_path)]

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    filter_script.unlink(missing_ok=True)
    if proc.returncode != 0 or not video_path.is_file():
        raise RuntimeError(f"Synthetic video generation failed: {proc.stderr}")

    schedule_path.write_text(json.dumps(schedule, indent=2))
    return video_path, schedule_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a synthetic cricket match video")
    parser.add_argument("--out", "--out-dir", dest="out", default="./data/synthetic")
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--order", choices=["runs-wickets", "wickets-runs"],
                        default="runs-wickets")
    parser.add_argument("--no-scorebox", action="store_true")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--distractor", action="store_true")
    args = parser.parse_args(argv)

    vid, sched = generate_synthetic_video(
        output_dir=args.out, duration_s=args.duration, has_audio=not args.no_audio,
        order=args.order, distractor=args.distractor, seed=args.seed,
        scorebox=not args.no_scorebox,
    )
    print(f"Generated synthetic video: {vid}")
    print(f"Generated schedule: {sched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
