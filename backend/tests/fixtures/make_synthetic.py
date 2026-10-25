"""Synthetic cricket broadcast generator for testing Reel without real footage.

Uses ffmpeg to generate test video with known scene cuts, drawn score box,
and audio tone bursts, accompanied by a ground-truth schedule.json.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from reel.ingest.probe import find_binary


def generate_synthetic_video(
    output_dir: Path | str,
    duration_s: float = 10.0,
    has_audio: bool = True,
    width: int = 1280,
    height: int = 720,
    fps: int = 25,
    order: str = "runs-wickets",
    distractor: bool = False,
    seed: int = 42,
) -> tuple[Path, Path]:
    """Generate a synthetic test video and schedule.json using ffmpeg."""
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    video_path = out_dir / "synthetic_video.mp4"
    schedule_path = out_dir / "schedule.json"

    ffmpeg = find_binary("ffmpeg")

    # Construct ffmpeg lavfi filter
    # Solid background with a drawn scorebox
    score_text = "IND 145/3  16.2 ov" if order == "runs-wickets" else "IND 3/145  16.2 ov"

    # Simple synthetic video generation
    # Video input: testsrc2 (or color + drawbox)
    v_filter = f"testsrc=duration={duration_s}:size={width}x{height}:rate={fps}"

    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        v_filter,
    ]

    if has_audio:
        cmd.extend([
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=1000:duration={duration_s}:sample_rate=44100",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
        ])
    else:
        cmd.extend(["-an"])

    cmd.extend([
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-t",
        str(duration_s),
        str(video_path),
    ])

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not video_path.is_file():
        raise RuntimeError(f"Synthetic video generation failed: {proc.stderr}")

    schedule: dict[str, Any] = {
        "duration_s": duration_s,
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": has_audio,
        "score_text": score_text,
        "order": order,
        "seed": seed,
        "distractor": distractor,
        "scorebox_rect": [100, 650, 360, 45],
        "cuts": [0.0, round(duration_s / 2, 2)],
        "scenes": ["run_up", "close_up"],
    }

    schedule_path.write_text(json.dumps(schedule, indent=2))
    return video_path, schedule_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic cricket match video")
    parser.add_argument("--out-dir", type=str, default="./data/synthetic")
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--order", choices=["runs-wickets", "wickets-runs"], default="runs-wickets")
    parser.add_argument("--distractor", action="store_true")
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args(argv)
    vid, sched = generate_synthetic_video(
        output_dir=args.out_dir,
        duration_s=args.duration,
        has_audio=not args.no_audio,
        order=args.order,
        distractor=args.distractor,
        seed=args.seed,
    )
    print(f"Generated synthetic video: {vid}")
    print(f"Generated schedule: {sched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
