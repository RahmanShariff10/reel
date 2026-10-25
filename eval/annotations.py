"""Timestamp annotations for real matches: format, loading and validation.

One CSV per match in ``eval/annotations/<match_id>.csv``::

    match_id,innings,over_ball,type,t_start_s,t_moment_s
    ipl24-m12,1,4.3,wicket,812.0,818.5

- ``over_ball``: over and ball as in commentary (``16.2``; ball 1-9 allows extras).
- ``type``: ``four``, ``six``, ``wicket`` or ``near_miss``.
- ``t_start_s``: video time the bowler starts running in; ``t_moment_s``: the hit/outcome.

Validate with ``uv run --project backend python -m eval.annotations <file.csv>``.
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

COLUMNS = ["match_id", "innings", "over_ball", "type", "t_start_s", "t_moment_s"]
TYPES = {"four", "six", "wicket", "near_miss"}
_OVER_BALL = re.compile(r"^\d{1,2}\.[1-9]$")


@dataclass(frozen=True)
class Annotation:
    match_id: str
    innings: int
    over_ball: str
    type: str
    t_start_s: float
    t_moment_s: float


def validate(path: Path | str) -> list[str]:
    """Return a list of problems as ``"line N: message"``; empty means valid."""
    problems: list[str] = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        missing = [c for c in COLUMNS if c not in header]
        if missing:
            return [f"line 1: missing column(s): {', '.join(missing)}"]
        for line, row in enumerate(reader, start=2):
            if row["innings"] not in ("1", "2"):
                problems.append(f"line {line}: innings must be 1 or 2, got {row['innings']!r}")
            if not _OVER_BALL.match(row["over_ball"] or ""):
                problems.append(
                    f"line {line}: bad over_ball {row['over_ball']!r} (expected e.g. 16.2)"
                )
            if row["type"] not in TYPES:
                problems.append(
                    f"line {line}: type must be one of {sorted(TYPES)}, got {row['type']!r}"
                )
            try:
                start, moment = float(row["t_start_s"]), float(row["t_moment_s"])
            except (TypeError, ValueError):
                problems.append(f"line {line}: t_start_s and t_moment_s must be numbers")
                continue
            if start < 0 or moment < 0:
                problems.append(f"line {line}: times must be >= 0")
            elif start > moment:
                problems.append(f"line {line}: t_start_s is after t_moment_s")
    return problems


def load(path: Path | str) -> list[Annotation]:
    """Load a valid annotation file; raises ValueError listing problems otherwise."""
    problems = validate(path)
    if problems:
        raise ValueError("; ".join(problems))
    with open(path, newline="") as fh:
        return [
            Annotation(
                r["match_id"],
                int(r["innings"]),
                r["over_ball"],
                r["type"],
                float(r["t_start_s"]),
                float(r["t_moment_s"]),
            )
            for r in csv.DictReader(fh)
        ]


def main(argv: list[str] | None = None) -> int:
    files = argv if argv is not None else sys.argv[1:]
    status = 0
    for f in files:
        problems = validate(f)
        print(f"{f}: {'OK' if not problems else f'{len(problems)} problem(s)'}")
        for p in problems:
            print(f"  {p}")
        status |= bool(problems)
    return status


if __name__ == "__main__":
    sys.exit(main())
