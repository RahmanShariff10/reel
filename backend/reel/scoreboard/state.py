"""Match-state machine: raw score readings → cleaned timeline and score events.

Rules (thresholds in ``config.scoreboard``):

- Confirmation: a new score is accepted only after it persists for
  ``consecutive_confirm`` consecutive readings (one-off misreads are dropped). Readings
  are counted rather than "changed crops", because unchanged crops reuse the previous
  reading and would otherwise never confirm a real change.
- Plausibility: runs never decrease within an innings; wickets rise by at most 1;
  a run jump above ``max_run_jump`` is rejected; overs going backwards are ignored.
- New innings: runs, wickets and overs all drop to near zero.
- DRS: wickets dropping by exactly 1 within ``drs_window_s`` of a wicket marks that
  wicket ``overturned`` and emits ``wicket_overturned``.
- Hidden box (``visible: false``): no events; the state carries on when it reappears.
"""

from __future__ import annotations

from dataclasses import dataclass

from reel.common.config import ScoreboardConfig
from reel.common.models import ScoreEvent, ScoreReading, ScoreTimelineEntry


@dataclass(frozen=True)
class _Score:
    runs: int
    wickets: int
    overs: float | None


def _same(a: _Score, b: _Score) -> bool:
    return (
        a.runs == b.runs
        and a.wickets == b.wickets
        and (a.overs is None or b.overs is None or a.overs == b.overs)
    )


def _overs_value(overs: float | None) -> int | None:
    if overs is None:
        return None
    tenths = round(overs * 10)
    return (tenths // 10) * 6 + tenths % 10


class MatchState:
    def __init__(self, cfg: ScoreboardConfig) -> None:
        self.cfg = cfg
        self.current: _Score | None = None
        self.innings = 1
        self.events: list[ScoreEvent] = []
        self._candidate: _Score | None = None
        self._candidate_t = 0.0
        self._candidate_n = 0
        self._last_wicket: int | None = None  # index into self.events

    # -- transitions -------------------------------------------------------------

    def _is_new_innings(self, old: _Score, new: _Score) -> bool:
        balls = _overs_value(new.overs)
        return (
            self.innings == 1
            and new.runs < old.runs
            and new.runs <= self.cfg.new_innings_max_runs
            and new.wickets <= 1
            and (balls is None or balls <= 12)
        )

    def _event(
        self, t: float, type_: str, new: _Score, runs_delta: int = 0, wicket_delta: int = 0
    ) -> None:
        self.events.append(
            ScoreEvent(
                type=type_,
                time_s=round(t, 3),
                runs_delta=runs_delta,
                wicket_delta=wicket_delta,
                runs=new.runs,
                wickets=new.wickets,
                overs=new.overs,
                innings=self.innings,
            )
        )

    def _apply(self, t: float, new: _Score) -> None:
        old = self.current
        assert old is not None
        if self._is_new_innings(old, new):
            self.innings = 2
            self._last_wicket = None
            self._event(t, "innings_start", new)
            self.current = new
            return

        drs = (
            new.wickets == old.wickets - 1
            and new.runs >= old.runs
            and self._last_wicket is not None
            and t - self.events[self._last_wicket].time_s <= self.cfg.drs_window_s
        )
        if drs:
            wicket = self.events[self._last_wicket]
            self.events[self._last_wicket] = wicket.model_copy(update={"overturned": True})
            self._last_wicket = None
            self._event(t, "wicket_overturned", new, wicket_delta=-1)
            self.current = new
            return

        old_balls, new_balls = _overs_value(old.overs), _overs_value(new.overs)
        if (
            new.runs < old.runs
            or new.wickets < old.wickets
            or new.wickets > old.wickets + 1
            or new.runs - old.runs > self.cfg.max_run_jump
            or (old_balls is not None and new_balls is not None and new_balls < old_balls)
        ):
            return  # implausible: keep the current state

        if new.runs > old.runs:
            self._event(t, "runs", new, runs_delta=new.runs - old.runs)
        if new.wickets == old.wickets + 1:
            self._event(t, "wicket", new, wicket_delta=1)
            self._last_wicket = len(self.events) - 1
        overs = new.overs if new.overs is not None else old.overs
        self.current = _Score(new.runs, new.wickets, overs)

    # -- feeding -----------------------------------------------------------------

    def feed(self, r: ScoreReading) -> None:
        if not r.visible or r.runs is None or r.wickets is None:
            return
        score = _Score(r.runs, r.wickets, r.overs)
        if self.current is not None and _same(score, self.current):
            self._candidate, self._candidate_n = None, 0
            if score.overs is not None and self.current.overs is None:
                self.current = score
            return
        if self._candidate is not None and _same(score, self._candidate):
            self._candidate_n += 1
        else:
            self._candidate, self._candidate_t, self._candidate_n = score, r.time_s, 1
        if self._candidate_n >= self.cfg.consecutive_confirm:
            if self.current is None:
                self.current = self._candidate  # initial score: no event
            else:
                self._apply(self._candidate_t, self._candidate)
            self._candidate, self._candidate_n = None, 0


def build_timeline(
    readings: list[ScoreReading], cfg: ScoreboardConfig
) -> tuple[list[ScoreTimelineEntry], list[ScoreEvent]]:
    """Run the state machine over readings (any order) → (timeline, events)."""
    state = MatchState(cfg)
    timeline: list[ScoreTimelineEntry] = []
    for r in sorted(readings, key=lambda r: r.time_s):
        state.feed(r)
        cur = state.current
        timeline.append(
            ScoreTimelineEntry(
                time_s=r.time_s,
                runs=cur.runs if cur else 0,
                wickets=cur.wickets if cur else 0,
                overs=(cur.overs or 0.0) if cur else 0.0,
                visible=r.visible,
                innings=state.innings,
            )
        )
    return timeline, state.events
