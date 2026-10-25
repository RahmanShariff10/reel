"""Tests for slice-18-highlight-rating.

Acceptance criteria:
- Exactly one event per wicket, six and four, with the configured base importance.
- Excitement, replay and death-overs bonuses are applied; the replay bonus is capped at
  0.15; importance never exceeds 1.0.
- Every wicket/six/four event has a score reason; every reason has a readable label.
- A changed weight in config changes the output with no code change.
- signals.audio false → no audio bonus or reason.
- signals.score false → only moment events.
- The same input gives identical events.
"""

from __future__ import annotations

import pytest

from reel.common.config import load_config
from reel.common.models import Delivery
from reel.highlights.rating import rate


def d(
    i: int,
    runs: int = 0,
    wicket: bool = False,
    overs: str = "5.1",
    excitement: float = 0.0,
    replays: int = 0,
    innings: int = 1,
    score: str = "IND 50/1",
    overturned: bool = False,
):
    return Delivery(
        id=f"d{i}",
        innings=innings,
        over_ball=overs,
        start_s=i * 30.0,
        t_hit_s=i * 30.0 + 5,
        end_s=i * 30.0 + 30,
        runs_delta=runs,
        wicket=wicket,
        overturned=overturned,
        score_after=score,
        replay_count=replays,
        excitement_max=excitement,
    )


DELIVERIES = [d(0, runs=1), d(1, runs=4), d(2), d(3, wicket=True), d(4, runs=6), d(5, runs=2)]


class TestTypes:
    def test_one_event_per_key_ball_with_base(self) -> None:
        cfg = load_config()
        events = rate(DELIVERIES, cfg)
        assert [(e.delivery_id, e.type) for e in events] == [
            ("d1", "four"),
            ("d3", "wicket"),
            ("d4", "six"),
        ]
        base = cfg.highlights.base_importance
        assert [e.importance for e in events] == [base.four, base.wicket, base.six]

    def test_score_reason_and_labels(self) -> None:
        for e in rate(DELIVERIES + [d(9, runs=4, excitement=0.8, replays=2)], load_config()):
            assert any(r.signal == "score" for r in e.reasons)
            assert all(r.label and r.label.strip() for r in e.reasons)

    def test_overturned_wicket_flagged(self) -> None:
        (event,) = rate([d(0, wicket=True, overturned=True)], load_config())
        assert event.overturned and "overturned" in event.reasons[0].label


class TestBonuses:
    def test_bonuses_and_caps(self) -> None:
        cfg = load_config()
        b = cfg.highlights.bonus
        (four,) = rate([d(0, runs=4, excitement=0.5, replays=5, overs="18.2")], cfg)
        expected = (
            cfg.highlights.base_importance.four + 0.5 * b.excitement_max + 0.15 + b.late_overs
        )
        assert four.importance == pytest.approx(min(1.0, expected))
        labels = {r.signal: r.label for r in four.reasons}
        assert labels["replays"] == "5 replays" and labels["match"] == "last 3 overs"
        (six,) = rate([d(0, runs=6, excitement=1.0, replays=3, overs="19.5")], cfg)
        assert six.importance == 1.0

    def test_close_chase(self) -> None:
        first = d(0, runs=1, score="IND 180/5", overs="19.6")
        chase = d(1, runs=6, innings=2, score="AUS 170/6", overs="18.3")
        events = rate([first, chase], load_config())
        assert events[0].reasons[-1].label == "close chase"

    def test_config_weight_changes_output(self) -> None:
        cfg = load_config(overrides={"highlights": {"base_importance": {"four": 0.3}}})
        (event,) = rate([d(0, runs=4)], cfg)
        assert event.importance == 0.3


class TestSignals:
    def test_audio_off(self) -> None:
        cfg = load_config(overrides={"signals": {"audio": False}})
        (event,) = rate([d(0, runs=4, excitement=0.9)], cfg)
        assert event.importance == cfg.highlights.base_importance.four
        assert all(r.signal != "audio" for r in event.reasons)

    def test_score_off_gives_moments(self) -> None:
        cfg = load_config()
        dels = [d(0, runs=4, excitement=0.9), d(1, runs=6), d(2, replays=1, excitement=0.2)]
        events = rate(dels, cfg, use_score=False)
        assert [e.type for e in events] == ["moment", "moment"]
        assert [e.delivery_id for e in events] == ["d0", "d2"]

    def test_deterministic(self) -> None:
        cfg = load_config()
        assert rate(DELIVERIES, cfg) == rate(list(reversed(DELIVERIES)), cfg)
