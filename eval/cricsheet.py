"""Load Cricsheet ball-by-ball JSON (https://cricsheet.org) as ground-truth balls."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Dismissals that do not add a wicket to the score graphic
NOT_WICKETS = {"retired hurt", "retired not out"}
ILLEGAL = ("wides", "noballs")


@dataclass(frozen=True)
class Ball:
    """One delivery from a Cricsheet match file."""

    innings: int  # 1 or 2
    over: int  # 0-based over index
    ball_in_over: int  # 1-based delivery number within the over (incl. wides/no-balls)
    legal_balls_after: int  # legal balls bowled in the innings after this delivery
    total_runs: int
    batter_runs: int
    extras: dict[str, int]
    wicket: bool
    legal: bool

    @property
    def over_ball(self) -> str:
        """Over and ball as written in commentary, e.g. ``16.2`` (wides share the next ball)."""
        return f"{self.over}.{self.ball_in_over}"

    @property
    def score_overs_after(self) -> str:
        """Overs shown on the score graphic after this delivery, e.g. ``16.2`` or ``17.0``."""
        return f"{self.legal_balls_after // 6}.{self.legal_balls_after % 6}"

    @property
    def is_four(self) -> bool:
        byes = self.extras.get("byes", 0) + self.extras.get("legbyes", 0)
        return self.batter_runs == 4 or byes == 4

    @property
    def is_six(self) -> bool:
        return self.batter_runs == 6

    @property
    def type(self) -> str | None:
        """Highlight type of this ball: ``wicket``, ``six``, ``four`` or None."""
        if self.wicket:
            return "wicket"
        if self.is_six:
            return "six"
        if self.is_four:
            return "four"
        return None


def load_balls(path: Path | str) -> list[Ball]:
    """Read every delivery of the first two innings (super overs are ignored)."""
    data = json.loads(Path(path).read_text())
    balls: list[Ball] = []
    for innings_no, innings in enumerate(data.get("innings", [])[:2], start=1):
        if innings.get("super_over"):
            continue
        legal = 0
        for over in innings.get("overs", []):
            last_legal = legal
            for d in over.get("deliveries", []):
                extras = {k: int(v) for k, v in d.get("extras", {}).items()}
                is_legal = not any(k in extras for k in ILLEGAL)
                legal += is_legal
                wickets = [w for w in d.get("wickets", []) if w.get("kind") not in NOT_WICKETS]
                balls.append(
                    Ball(
                        innings=innings_no,
                        over=int(over["over"]),
                        ball_in_over=legal - last_legal + (0 if is_legal else 1),
                        legal_balls_after=legal,
                        total_runs=int(d["runs"]["total"]),
                        batter_runs=int(d["runs"]["batter"]),
                        extras=extras,
                        wicket=bool(wickets),
                        legal=is_legal,
                    )
                )
    return balls


def counts(balls: list[Ball]) -> dict[int, dict[str, int]]:
    """Fours, sixes and wickets per innings."""
    out: dict[int, dict[str, int]] = {}
    for b in balls:
        row = out.setdefault(b.innings, {"four": 0, "six": 0, "wicket": 0})
        if b.type:
            row[b.type] += 1
    return out
