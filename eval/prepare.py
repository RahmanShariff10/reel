"""Prepare SoccerNet matches by joining half videos into match.mkv."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def find_binary(name: str) -> str:
    """Find a system binary, checking PATH and common macOS / Linux locations."""
    path = shutil.which(name)
    if path:
        return path

    candidates = [
        Path("/opt/homebrew/bin") / name,
        Path("/usr/local/bin") / name,
        Path("/usr/bin") / name,
        Path(os.path.expanduser("~/.local/bin")) / name,
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)

    raise FileNotFoundError(
        f"Required binary '{name}' not found on PATH. Please install ffmpeg/ffprobe."
    )


def probe_duration(path: Path | str) -> float:
    """Probe duration in seconds of a video file using ffprobe."""
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    ffprobe = find_binary("ffprobe")
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(p),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(proc.stdout)
    d = info.get("format", {}).get("duration")
    if d is not None:
        return float(d)

    cmd_s = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=duration",
        "-of",
        "json",
        str(p),
    ]
    proc = subprocess.run(cmd_s, capture_output=True, text=True, check=True)
    info = json.loads(proc.stdout)
    streams = info.get("streams", [])
    if streams and "duration" in streams[0]:
        return float(streams[0]["duration"])

    raise ValueError(f"Could not determine duration of {path}")


def find_half_files(game: str | Path, videos_dir: str | Path | None = None) -> tuple[Path, Path]:
    """Locate 1_720p.mkv and 2_720p.mkv for a given game."""
    g_path = Path(game)
    v_path = Path(videos_dir) if videos_dir else None

    candidates: list[Path] = []
    if v_path:
        candidates.append(v_path / g_path)
    candidates.append(g_path)
    if v_path:
        candidates.append(v_path)

    for base in candidates:
        for ext in (".mkv", ".mp4"):
            h1 = base / f"1_720p{ext}"
            h2 = base / f"2_720p{ext}"
            if h1.is_file() and h2.is_file():
                return h1, h2

    # Check without _720p suffix
    for base in candidates:
        for ext in (".mkv", ".mp4"):
            h1 = base / f"1{ext}"
            h2 = base / f"2{ext}"
            if h1.is_file() and h2.is_file():
                return h1, h2

    searched = [str(c) for c in candidates]
    raise FileNotFoundError(f"Could not find half videos for game '{game}' in {searched}")


def join_halves(half1: Path, half2: Path, out_mkv: Path) -> None:
    """Concatenate two half videos using ffmpeg stream copy into match.mkv."""
    ffmpeg = find_binary("ffmpeg")
    out_mkv.parent.mkdir(parents=True, exist_ok=True)

    concat_list = out_mkv.parent / f".concat_{out_mkv.stem}.txt"
    p1 = str(half1.resolve()).replace("'", "'\\''")
    p2 = str(half2.resolve()).replace("'", "'\\''")
    concat_list.write_text(f"file '{p1}'\nfile '{p2}'\n", encoding="utf-8")

    cmd = [
        ffmpeg,
        "-y",
        "-v",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-c",
        "copy",
        str(out_mkv),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg join failed: {proc.stderr}")
    finally:
        concat_list.unlink(missing_ok=True)


def prepare_match(
    game: str | Path,
    videos_dir: str | Path | None,
    out_dir: str | Path,
) -> dict[str, Any]:
    """Join halves into match.mkv and write match.json with first_half_s."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    half1, half2 = find_half_files(game, videos_dir)
    first_half_s = probe_duration(half1)
    second_half_s = probe_duration(half2)

    out_mkv = out / "match.mkv"
    join_halves(half1, half2, out_mkv)
    joined_duration_s = probe_duration(out_mkv)

    metadata: dict[str, Any] = {
        "game": str(game),
        "first_half_s": first_half_s,
        "second_half_s": second_half_s,
        "duration_s": joined_duration_s,
    }

    match_json = out / "match.json"
    match_json.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main(argv: list[str] | None = None) -> int:
    """CLI for preparing a SoccerNet match."""
    parser = argparse.ArgumentParser(
        description="Join SoccerNet 1_720p.mkv and 2_720p.mkv into match.mkv"
    )
    parser.add_argument("--game", required=True, help="SoccerNet path or game name")
    parser.add_argument(
        "--videos", default=None, help="Root directory containing SoccerNet videos"
    )
    parser.add_argument(
        "--out", required=True, help="Output directory for match.mkv and match.json"
    )
    args = parser.parse_args(argv)

    meta = prepare_match(game=args.game, videos_dir=args.videos, out_dir=args.out)
    print(
        f"Prepared {args.game}: first_half_s={meta['first_half_s']:.1f}s, "
        f"duration={meta['duration_s']:.1f}s -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
