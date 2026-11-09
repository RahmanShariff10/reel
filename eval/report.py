"""Aggregate evaluation report across matches, against the PRD targets.

    uv run --project backend python -m eval.report --manifest eval/manifests/matches.yaml

Each evaluated manifest entry needs a ``job_id`` (the Reel job that processed it). Labels are read
from ``--labels/<game>/Labels-v2.json`` and the first half's length from
``--prepared/<game>/match.json``, written by ``eval.prepare``. Output is numbers only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from reel.common.config import load_config
from reel.common.models import (
    Event,
    Meta,
    ReelPlan,
    Scorebox,
    ScoreTimelineEntry,
    Summary,
    is_valid,
    read_model,
)
from reel.common.paths import JobPaths

from eval.metrics import (
    Coverage,
    Detection,
    ReelQuality,
    e1_goals,
    e2_key_actions,
    e3_goal_clips,
    e5_reel_quality,
    goal_times,
    in_play_intervals,
    key_action_times,
)
from eval.soccernet import ManifestEntry, load_labels, load_manifest

EVAL_DIR = Path(__file__).parent
REPORTS_DIR = EVAL_DIR / "reports"

SCORE_FOUND = "Score graphic found"
GOAL_RECALL = "Goals found (E1 recall)"
GOAL_PRECISION = "Detected goals that are real (E1 precision)"
KEY_ACTIONS_FOUND = "Key actions found (E2)"
GOAL_CLIPS = "Goal clips containing the goal (E3)"
REEL_QUALITY = "Reel clips with a key action (E5)"
PROCESSING = "Processing time (s)"

TARGETS: dict[str, tuple[float, str]] = {
    SCORE_FOUND: (0.90, ">="),
    GOAL_RECALL: (0.95, ">="),
    GOAL_PRECISION: (0.95, ">="),
    KEY_ACTIONS_FOUND: (0.70, ">="),
    GOAL_CLIPS: (0.85, ">="),
    REEL_QUALITY: (0.60, ">="),
    PROCESSING: (3600.0, "<="),
}


@dataclass
class MatchResult:
    game: str
    found: bool
    goals: Detection
    key_actions: Coverage
    goal_clips: Coverage
    reel: ReelQuality | None
    processing_s: float | None

    def metric(self, name: str) -> float | None:
        return {
            SCORE_FOUND: 1.0 if self.found else 0.0,
            GOAL_RECALL: self.goals.recall,
            GOAL_PRECISION: self.goals.precision,
            KEY_ACTIONS_FOUND: self.key_actions.ratio,
            GOAL_CLIPS: self.goal_clips.ratio,
            REEL_QUALITY: self.reel.share if self.reel else None,
            PROCESSING: self.processing_s,
        }[name]


def evaluate_match(
    entry: ManifestEntry, data_dir: Path, labels_root: Path, prepared_root: Path
) -> MatchResult:
    paths = JobPaths(entry.job_id, data_dir=data_dir)
    labels = load_labels(labels_root / entry.game / "Labels-v2.json")
    first_half_s = float(
        json.loads((prepared_root / entry.game / "match.json").read_text())["first_half_s"]
    )
    goals = goal_times(labels, first_half_s)
    actions = key_action_times(labels, first_half_s)
    events = read_model(paths.events_json, list[Event])
    found = read_model(paths.scorebox_json, Scorebox).found

    reel = None
    plan_path = paths.reel_plan_path("5min")
    if is_valid(plan_path, ReelPlan):
        timeline = (
            read_model(paths.score_timeline_json, list[ScoreTimelineEntry])
            if is_valid(paths.score_timeline_json, list[ScoreTimelineEntry])
            else []
        )
        duration = read_model(paths.meta_json, Meta).duration_s
        reel = e5_reel_quality(
            read_model(plan_path, ReelPlan), actions, in_play_intervals(timeline, duration)
        )

    processing = (
        read_model(paths.summary_json, Summary).processing_s
        if is_valid(paths.summary_json, Summary)
        else None
    )
    return MatchResult(
        game=entry.game,
        found=found,
        goals=e1_goals(events, goals),
        key_actions=e2_key_actions(events, actions, found),
        goal_clips=e3_goal_clips(events, goals),
        reel=reel,
        processing_s=processing,
    )


def _overall(results: list[MatchResult], name: str) -> float | None:
    """Goals are rare, so counts are pooled across matches rather than averaging ratios."""
    if not results:
        return None
    if name == GOAL_RECALL or name == GOAL_PRECISION:
        pooled = Detection(
            tp=sum(r.goals.tp for r in results),
            fp=sum(r.goals.fp for r in results),
            fn=sum(r.goals.fn for r in results),
        )
        return pooled.recall if name == GOAL_RECALL else pooled.precision
    if name == KEY_ACTIONS_FOUND or name == GOAL_CLIPS:
        parts = [r.key_actions if name == KEY_ACTIONS_FOUND else r.goal_clips for r in results]
        return Coverage(sum(p.found for p in parts), sum(p.total for p in parts)).ratio
    values = [v for v in (r.metric(name) for r in results) if v is not None]
    if not values:
        return None
    return max(values) if name == PROCESSING else sum(values) / len(values)


def _met(value: float | None, target: tuple[float, str]) -> str:
    if value is None:
        return "n/a"
    goal, op = target
    return "met" if (value >= goal if op == ">=" else value <= goal) else "not met"


def _fmt(name: str, value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.0f}" if name == PROCESSING else f"{value:.3f}"


def _short(game: str) -> str:
    return game.rstrip("/").split("/")[-1]


def write_reports(
    results: list[MatchResult], skipped: list[str], out_dir: Path = REPORTS_DIR
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    header = ["Metric", "Target", *[_short(r.game) for r in results], "Overall", "Result"]
    rows = []
    for name, target in TARGETS.items():
        goal, op = target
        overall = _overall(results, name)
        rows.append(
            [
                name,
                f"{op} {goal:.0f}" if name == PROCESSING else f"{op} {goal:.2f}",
                *[_fmt(name, r.metric(name)) for r in results],
                _fmt(name, overall),
                _met(overall, target),
            ]
        )

    md = [
        "# Evaluation summary",
        "",
        f"{len(results)} match(es) evaluated. Numbers only: no frames or clips.",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
        *["| " + " | ".join(row) + " |" for row in rows],
    ]
    md += [
        "",
        "## Goals (E1)",
        "",
        "| Match | True positives | False positives | Missed |",
        "|---|---|---|---|",
    ]
    md += [
        f"| {_short(r.game)} | {r.goals.tp} | {r.goals.fp} | {r.goals.fn} |" for r in results
    ]
    md += [
        "",
        "## Reel against random clips (E5)",
        "",
        "Compare the two shares yourself: the PRD asks for a reel clearly better than random.",
        "",
        "| Match | Clips | With key action | Share | Random share |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        if r.reel is None:
            md.append(f"| {_short(r.game)} | n/a | n/a | n/a | n/a |")
            continue
        random_share = "n/a" if r.reel.random_share is None else f"{r.reel.random_share:.3f}"
        share = _fmt(REEL_QUALITY, r.reel.share)
        md.append(
            f"| {_short(r.game)} | {r.reel.clips} | {r.reel.with_action} | {share} "
            f"| {random_share} |"
        )
    if skipped:
        md += ["", "## Not evaluated (no job_id)", ""]
        md += [f"- {_short(game)}" for game in skipped]

    md_path, csv_path = out_dir / "summary.md", out_dir / "summary.csv"
    md_path.write_text("\n".join(md) + "\n")
    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return md_path, csv_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate evaluation report")
    parser.add_argument("--manifest", type=Path, default=EVAL_DIR / "manifests" / "matches.yaml")
    parser.add_argument("--split", default="test", help="which split to evaluate (default: test)")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--labels", type=Path, default=EVAL_DIR / "soccernet")
    parser.add_argument("--prepared", type=Path, default=Path("data/soccernet/prepared"))
    parser.add_argument("--out-dir", type=Path, default=REPORTS_DIR)
    args = parser.parse_args(argv)

    entries = [e for e in load_manifest(args.manifest) if e.split == args.split]
    ready = [e for e in entries if e.job_id]
    skipped = [e.game for e in entries if not e.job_id]
    data_dir = args.data_dir or Path(load_config().data_dir)
    results = [evaluate_match(e, data_dir, args.labels, args.prepared) for e in ready]
    md_path, _ = write_reports(results, skipped, args.out_dir)
    print(md_path.read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
