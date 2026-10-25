"""Aggregate evaluation report across matches (E1, E2, E3, runtime vs PRD targets).

    uv run --project backend python -m eval.report [--manifest eval/matches.yaml] [--matches m1,m2]

The manifest lists each evaluated match::

    matches:
      - match_id: ipl24-m12
        job_id: job-1a2b3c4d5e6f
        cricsheet: eval/cricsheet/1426312.json
        annotations: eval/annotations/ipl24-m12.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml
from reel.common.config import load_config
from reel.common.models import Delivery, Event, ScoreEvent, Summary, read_model
from reel.common.paths import JobPaths

from eval import annotations as ann
from eval.cricsheet import load_balls
from eval.e1 import TYPES, TypeScore, detected_events, score
from eval.metrics import E2, E3, e2_deliveries, e3_clips

EVAL_DIR = Path(__file__).parent
REPO = EVAL_DIR.parent
REPORTS_DIR = EVAL_DIR / "reports"

# PRD success criteria
TARGETS = {
    "E1 recall (boundaries + wickets found)": (0.90, ">="),
    "E1 precision (detected events real)": (0.90, ">="),
    "E2 delivery recall": (0.90, ">="),
    "E3 clips containing the moment": (0.85, ">="),
    "Processing time (s)": (3600.0, "<="),
}


@dataclass
class MatchResult:
    match_id: str
    e1: dict[str, TypeScore]
    e2: E2 | None
    e3: E3 | None
    processing_s: float | None

    def metric(self, name: str) -> float | None:
        total = TypeScore(
            tp=sum(s.tp for s in self.e1.values()),
            fp=sum(s.fp for s in self.e1.values()),
            fn=sum(s.fn for s in self.e1.values()),
        )
        return {
            "E1 recall (boundaries + wickets found)": total.recall,
            "E1 precision (detected events real)": total.precision,
            "E2 delivery recall": self.e2.recall if self.e2 else None,
            "E3 clips containing the moment": self.e3.contained_ratio if self.e3 else None,
            "Processing time (s)": self.processing_s,
        }[name]


def _path(p: str | None) -> Path | None:
    if not p:
        return None
    path = Path(p)
    return path if path.is_absolute() else REPO / path


def evaluate_match(entry: dict, data_dir: Path) -> MatchResult:
    paths = JobPaths(entry["job_id"], data_dir=data_dir)
    balls = load_balls(_path(entry["cricsheet"]))
    events = read_model(paths.score_events_json, list[ScoreEvent])
    e1 = score(detected_events(events), balls)
    e2 = None
    if paths.deliveries_json.is_file():
        e2 = e2_deliveries(read_model(paths.deliveries_json, list[Delivery]), balls)
    e3 = None
    ann_path = _path(entry.get("annotations"))
    if ann_path and ann_path.is_file() and paths.events_json.is_file():
        e3 = e3_clips(ann.load(ann_path), read_model(paths.events_json, list[Event]))
    proc = (
        read_model(paths.summary_json, Summary).processing_s
        if paths.summary_json.is_file()
        else None
    )
    return MatchResult(entry["match_id"], e1, e2, e3, proc)


def _met(value: float | None, target: tuple[float, str]) -> str:
    if value is None:
        return "n/a"
    goal, op = target
    ok = value >= goal if op == ">=" else value <= goal
    return "met" if ok else "not met"


def _fmt(name: str, value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.0f}" if name.startswith("Processing") else f"{value:.3f}"


def _overall(results: list[MatchResult], name: str) -> float | None:
    values = [r.metric(name) for r in results if r.metric(name) is not None]
    if not values:
        return None
    if name.startswith("Processing"):
        return max(values)  # worst case
    return sum(values) / len(values)


def write_reports(results: list[MatchResult], out_dir: Path = REPORTS_DIR) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    names = list(TARGETS)
    header = ["Metric", "Target", *[r.match_id for r in results], "Overall", "Result"]
    rows = []
    for name in names:
        goal, op = TARGETS[name]
        overall = _overall(results, name)
        target = f"{op} {goal:.0f}" if name.startswith("Processing") else f"{op} {goal:.2f}"
        rows.append(
            [
                name,
                target,
                *[_fmt(name, r.metric(name)) for r in results],
                _fmt(name, overall),
                _met(overall, TARGETS[name]),
            ]
        )

    md = [
        "# Evaluation summary",
        "",
        f"Matches: {', '.join(r.match_id for r in results)}",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    md += ["| " + " | ".join(row) + " |" for row in rows]
    md += [
        "",
        "## Per-type event detection (E1)",
        "",
        "| Match | Type | TP | FP | FN | Precision | Recall |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        for t in TYPES:
            s = r.e1[t]
            md.append(
                f"| {r.match_id} | {t} | {s.tp} | {s.fp} | {s.fn} | "
                f"{s.precision:.3f} | {s.recall:.3f} |"
            )
    md += [
        "",
        "## Clip timing (E3)",
        "",
        "| Match | Annotated | Contained | Median start offset (s) | P90 offset (s) | Missing |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        if r.e3:
            md.append(
                f"| {r.match_id} | {r.e3.total} | {r.e3.contained} | {r.e3.median_offset} "
                f"| {r.e3.p90_offset} | {', '.join(r.e3.missing) or '-'} |"
            )
    md += [
        "",
        "## Delivery detection (E2)",
        "",
        "| Match | Detected | Cricsheet balls | Matched | Precision | Recall | Gap |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r.e2:
            md.append(
                f"| {r.match_id} | {r.e2.detected} | {r.e2.truth} | {r.e2.matched} | "
                f"{r.e2.precision:.3f} | {r.e2.recall:.3f} | {r.e2.gap:+d} |"
            )

    md_path, csv_path = out_dir / "summary.md", out_dir / "summary.csv"
    md_path.write_text("\n".join(md) + "\n")
    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return md_path, csv_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate evaluation report")
    parser.add_argument("--manifest", type=Path, default=EVAL_DIR / "matches.yaml")
    parser.add_argument("--matches", default=None, help="comma-separated match ids (default all)")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=REPORTS_DIR)
    args = parser.parse_args(argv)

    entries = yaml.safe_load(args.manifest.read_text())["matches"]
    if args.matches:
        wanted = set(args.matches.split(","))
        entries = [e for e in entries if e["match_id"] in wanted]
    data_dir = args.data_dir or Path(load_config().data_dir)
    results = [evaluate_match(e, data_dir) for e in entries]
    md, _ = write_reports(results, args.out_dir)
    print(md.read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
