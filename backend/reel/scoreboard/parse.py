"""Parsing helpers for score-graphic text, e.g. ``ARS 1-0 CHE 67:05``.

- ``find_clock``: the match clock (``67:05``, ``45:00+2``).
- ``find_goals``: home and away goals, with or without a separator, including the ways OCR
  misreads zeros as the letter O on real broadcasts.
- ``parse_score``: both, plus the team codes either side of the score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
_CODE_RE = re.compile(r"[A-Za-z]{2,}")


@dataclass(frozen=True)
class ClockToken:
    """A match clock found in text, with its character span in that text."""

    seconds: int
    added_min: int | None
    start: int
    end: int


@dataclass(frozen=True)
class ScoreText:
    """What a piece of score-graphic text says; a field is None when it isn't there."""

    home: int | None = None
    away: int | None = None
    home_code: str | None = None
    away_code: str | None = None
    clock: ClockToken | None = None


def find_clock(text: str) -> ClockToken | None:
    """Return the first clock token in ``text`` (``67:05``, ``45:00+2``), if any."""
    m = _CLOCK_RE.search(text)
    if not m:
        return None
    added = int(m.group(3)) if m.group(3) else None
    return ClockToken(int(m.group(1)) * 60 + int(m.group(2)), added, m.start(), m.end())


def _goal_count(token: str) -> int:
    return int(token.replace("O", "0").replace("o", "0"))


def _without_clock(text: str) -> str:
    clock = find_clock(text)
    return text if clock is None else f"{text[: clock.start]} {text[clock.end :]}"


def _goals_match(text: str, max_goals: int) -> tuple[int, int, re.Match[str]] | None:
    """The score in clock-free text. The strongest pattern present decides: a separated score
    that is out of range means no score, rather than falling back to looser patterns
    (``16-0`` is not ``1-6``).
    """
    for pattern in _GOALS_PATTERNS:
        matches = list(pattern.finditer(text))
        if not matches:
            continue
        for m in matches:
            home, away = _goal_count(m.group(1)), _goal_count(m.group(2))
            if home <= max_goals and away <= max_goals:
                return home, away, m
        return None
    return None


def find_goals(text: str, max_goals: int = 15) -> tuple[int, int] | None:
    """Return (home, away) goals from score text, ignoring any clock in it."""
    found = _goals_match(_without_clock(text), max_goals)
    return None if found is None else (found[0], found[1])


def parse_score(text: str, max_goals: int = 15) -> ScoreText:
    """Parse goals, team codes and clock from score-graphic text.

    Text from several OCR items joined in reading order parses the same as one line. Team
    codes are the nearest letters before and after the score (``PARIS SG`` gives ``PARIS``).
    """
    clock = find_clock(text)
    rest = _without_clock(text)
    found = _goals_match(rest, max_goals)
    if found is None:
        return ScoreText(clock=clock)
    home, away, m = found
    before = _CODE_RE.findall(rest[: m.start()])
    after = _CODE_RE.findall(rest[m.end() :])
    return ScoreText(
        home=home,
        away=away,
        home_code=before[-1].upper() if before else None,
        away_code=after[0].upper() if after else None,
        clock=clock,
    )
