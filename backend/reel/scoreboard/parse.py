"""Parsing helpers for score-graphic text.

Football: ``find_clock`` and ``find_goals`` (e.g. ``ARS 1-0 CHE 67:05``).
Cricket (``IND 145/3  16.2``): the rest, used by the cricket reader until slice 40 replaces it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Football
# ---------------------------------------------------------------------------

# Clock token: M:SS, MM:SS or MMM:SS with seconds < 60, optionally "+N" added minutes.
# Seconds always have two digits, so a score such as "2:1" is never taken for a clock.
_CLOCK_RE = re.compile(r"(?<![\d:.])(\d{1,3}):([0-5]\d)(?:\s*\+\s*(\d{1,2}))?(?![\d:])")
# Goals separated by "-", ":" or "|". OCR often reads 0 as the letter O ("ARSO-O CHE").
_GOALS_SEP_RE = re.compile(r"(?<![\d:.])([\dOo]{1,2})\s*[-:|]\s*([\dOo]{1,2})(?![\d:.])")
# Goals separated by spaces only ("ARS 1 0 CHE"); digits only, as letters are too ambiguous.
_GOALS_SPACE_RE = re.compile(r"(?<![\d:.])(\d{1,2})\s+(\d{1,2})(?![\d:.])")
# OCR dropped the spaces ("ARS10CHE"), so two lone digits are one goal each.
_GOALS_JOINED_RE = re.compile(r"(?<![\d:.])(\d)(\d)(?![\d:.])")
# Zeros read as letters, as separate characters ("OM 0 O PARIS SG") or joined ("OM OO PARIS
# SG", "OOPARIS SG"). The pair must not follow a letter, so "GOOD" or "ROONEY" never count.
_GOALS_SPACE_O_RE = re.compile(r"(?<![A-Za-z\d:.])([\dOo])\s+([\dOo])(?![\d:.])")
_GOALS_JOINED_O_RE = re.compile(r"(?<![A-Za-z\d:.])([\dOo])([\dOo])(?![\d:.])")
_GOALS_PATTERNS = (
    _GOALS_SEP_RE,
    _GOALS_SPACE_RE,
    _GOALS_JOINED_RE,
    _GOALS_SPACE_O_RE,
    _GOALS_JOINED_O_RE,
)


@dataclass(frozen=True)
class ClockToken:
    """A match clock found in text, with its character span in that text."""

    seconds: int
    added_min: int | None
    start: int
    end: int


def find_clock(text: str) -> ClockToken | None:
    """Return the first clock token in ``text`` (``67:05``, ``45:00+2``), if any."""
    m = _CLOCK_RE.search(text)
    if not m:
        return None
    added = int(m.group(3)) if m.group(3) else None
    return ClockToken(int(m.group(1)) * 60 + int(m.group(2)), added, m.start(), m.end())


def _goal_count(token: str) -> int:
    return int(token.replace("O", "0").replace("o", "0"))


def find_goals(text: str, max_goals: int = 15) -> tuple[int, int] | None:
    """Return (home, away) goals from score text, ignoring any clock in it.

    The strongest pattern present decides: a separated score that is out of range means no
    score, rather than falling back to looser patterns (``16-0`` is not ``1-6``).
    """
    clock = find_clock(text)
    if clock is not None:
        text = f"{text[: clock.start]} {text[clock.end :]}"
    for pattern in _GOALS_PATTERNS:
        matches = list(pattern.finditer(text))
        if not matches:
            continue
        for m in matches:
            home, away = _goal_count(m.group(1)), _goal_count(m.group(2))
            if home <= max_goals and away <= max_goals:
                return home, away
        return None
    return None


# ---------------------------------------------------------------------------
# Cricket (removed with the cricket reader in slice 40)
# ---------------------------------------------------------------------------

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
