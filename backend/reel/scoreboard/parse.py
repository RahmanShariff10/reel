"""Parsing helpers for score-box text (e.g. ``IND 145/3  16.2``)."""

from __future__ import annotations

import re
from dataclasses import dataclass

# runs/wickets or wickets/runs pair, separated by "/" or "-"
_PAIR_RE = re.compile(r"(?<![\d.])(\d{1,3})\s*[/-]\s*(\d{1,3})(?![\d])")
# overs: 0-99 overs, 0-5 balls; not part of a longer number (rejects "8.25")
_OVERS_RE = re.compile(r"(?<![\d.])(\d{1,2})\.([0-5])(?![\d])")


# a pair whose second number ran into the overs, e.g. "145/215.3" (OCR dropped the space)
_MERGED_RE = re.compile(r"(\d{1,3}\s*[/-]\s*)(\d{2,4}\.[0-5])(?!\d)")


def _split_merged(m: re.Match[str]) -> str:
    digits, balls = m.group(2).split(".")
    for n in (1, 2):  # wickets are 0-10, overs at most two digits
        wickets, overs = digits[:n], digits[n:]
        if 0 < len(overs) <= 2 and int(wickets) <= 10:
            return f"{m.group(1)}{wickets} {overs}.{balls}"
    return m.group(0)


def normalize(text: str) -> str:
    """Re-insert the space OCR sometimes drops between the score and the overs."""
    return _MERGED_RE.sub(_split_merged, text)


@dataclass(frozen=True)
class ScorePair:
    """Two numbers of a score pair, in the order they appear on screen."""

    first: int
    second: int


def find_pair(text: str) -> ScorePair | None:
    """Return the first score-like ``a/b`` or ``a-b`` pair in ``text``, if any."""
    m = _PAIR_RE.search(normalize(text))
    if not m:
        return None
    return ScorePair(int(m.group(1)), int(m.group(2)))


def find_overs(text: str) -> float | None:
    """Return overs (e.g. ``16.2``) found in ``text``, ignoring the score pair."""
    stripped = _PAIR_RE.sub(" ", normalize(text))
    m = _OVERS_RE.search(stripped)
    if not m:
        return None
    return float(f"{int(m.group(1))}.{m.group(2)}")


_TEAM_RE = re.compile(r"\b([A-Z]{2,5})\b")


@dataclass(frozen=True)
class ParsedScore:
    """A score-box reading; fields are None when not present in the text."""

    team: str | None
    runs: int | None
    wickets: int | None
    overs: float | None


def parse_score(text: str, order: str | None = "runs-wickets") -> ParsedScore | None:
    """Parse runs, wickets, overs and team from score-box text.

    ``order`` says which number of the pair comes first on screen. Returns None when
    neither a plausible score pair nor overs are present.
    """
    clean = normalize(text)
    pair, overs = find_pair(clean), find_overs(clean)
    runs = wickets = None
    if pair is not None:
        runs, wickets = (
            (pair.second, pair.first) if order == "wickets-runs" else (pair.first, pair.second)
        )
        if wickets > 10:
            runs = wickets = None
    if runs is None and overs is None:
        return None
    team_match = _TEAM_RE.search(_PAIR_RE.sub(" ", clean).replace("OVERS", " "))
    team = team_match.group(1) if team_match and team_match.group(1) != "OV" else None
    return ParsedScore(team=team, runs=runs, wickets=wickets, overs=overs)
