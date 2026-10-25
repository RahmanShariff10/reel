"""E1 — event detection accuracy: our score events vs Cricsheet ground truth.

Score events are matched to Cricsheet balls by innings, event type and the overs shown on
the score graphic after the ball (e.g. ``16.2``). Reports precision / recall / F1 for
fours, sixes and wickets.

    uv run --project backend python -m eval.e1 --job <job_id> --cricsheet eval/cricsheet/<id>.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from reel.common.config import load_config
from reel.common.models import ScoreEvent, read_model
from reel.common.paths import JobPaths

from eval.cricsheet import Ball, load_balls

TYPES = ("four", "six", "wicket")
REPORTS_DIR = Path(__file__).parent / "reports"


@dataclass(frozen=True)
class Detected:
    innings: int
    type: str
    legal_balls: int | None  # from the overs on the score graphic; None if unreadable
    time_s: float


@dataclass
class TypeScore:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def _legal_balls(overs: float | None) -> int | None:
    if overs is None:
        return None
    tenths = round(overs * 10)
    return (tenths // 10) * 6 + tenths % 10


def detected_events(events: list[ScoreEvent]) -> list[Detected]:
    """Turn score events into fours, sixes and wickets (overturned wickets removed)."""
    out: list[Detected | None] = []
    open_wickets: dict[int, list[int]] = {}
    for ev in sorted(events, key=lambda e: e.time_s):
        kind = None
        if ev.type == "runs" and ev.runs_delta in (4, 6):
            kind = "four" if ev.runs_delta == 4 else "six"
        elif ev.type == "wicket":
            kind = "wicket"
        elif ev.type == "wicket_overturned":
            stack = open_wickets.get(ev.innings, [])
            if stack:
                out[stack.pop()] = None
            continue
        if kind:
            out.append(Detected(ev.innings, kind, _legal_balls(ev.overs), ev.time_s))
            if kind == "wicket":
                open_wickets.setdefault(ev.innings, []).append(len(out) - 1)
    return [d for d in out if d is not None]


def score(
    detected: list[Detected], balls: list[Ball], tolerance_balls: int = 0
) -> dict[str, TypeScore]:
    """Match detections to ground-truth balls of the same innings and type."""
    result = {t: TypeScore() for t in TYPES}
    for t in TYPES:
        truth = [b for b in balls if b.type == t]
        used = [False] * len(truth)
        for d in (d for d in detected if d.type == t):
            best, best_dist = None, None
            for i, b in enumerate(truth):
                if used[i] or b.innings != d.innings or d.legal_balls is None:
                    continue
                dist = abs(b.legal_balls_after - d.legal_balls)
                if dist <= tolerance_balls and (best_dist is None or dist < best_dist):
                    best, best_dist = i, dist
            if best is None:
                result[t].fp += 1
            else:
                used[best] = True
                result[t].tp += 1
        result[t].fn = used.count(False)
    return result


def report_markdown(match_id: str, scores: dict[str, TypeScore]) -> str:
    lines = [
        f"# E1 — event detection: {match_id}",
        "",
        "| Type | TP | FP | FN | Precision | Recall | F1 |",
        "|---|---|---|---|---|---|---|",
    ]
    total = TypeScore()
    for t in TYPES:
        s = scores[t]
        total.tp, total.fp, total.fn = total.tp + s.tp, total.fp + s.fp, total.fn + s.fn
        lines.append(
            f"| {t} | {s.tp} | {s.fp} | {s.fn} | {s.precision:.3f} | {s.recall:.3f} | {s.f1:.3f} |"
        )
    lines.append(
        f"| **all** | {total.tp} | {total.fp} | {total.fn} | {total.precision:.3f} "
        f"| {total.recall:.3f} | {total.f1:.3f} |"
    )
    return "\n".join(lines) + "\n"


def write_report(match_id: str, scores: dict[str, TypeScore], out_dir: Path = REPORTS_DIR) -> Path:
    dest = out_dir / match_id
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "e1.md").write_text(report_markdown(match_id, scores))
    payload = {
        t: {**asdict(s), "precision": s.precision, "recall": s.recall, "f1": s.f1}
        for t, s in scores.items()
    }
    (dest / "e1.json").write_text(json.dumps({"match_id": match_id, "types": payload}, indent=2))
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="E1: event detection vs Cricsheet")
    parser.add_argument("--job", required=True, help="job id whose score_events.json to score")
    parser.add_argument("--cricsheet", required=True, type=Path)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--match-id", default=None, help="defaults to the Cricsheet file name")
    parser.add_argument("--tolerance-balls", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=REPORTS_DIR)
    args = parser.parse_args(argv)

    paths = JobPaths(args.job, data_dir=args.data_dir or load_config().data_dir)
    events = read_model(paths.score_events_json, list[ScoreEvent])
    scores = score(detected_events(events), load_balls(args.cricsheet), args.tolerance_balls)
    match_id = args.match_id or args.cricsheet.stem
    dest = write_report(match_id, scores, args.out_dir)
    print(report_markdown(match_id, scores))
    print(f"Report written to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
