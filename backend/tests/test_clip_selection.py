"""Tests for slice-19-clip-selection.

Acceptance criteria:
- A boundary clip follows the rule: <= 25 s and ends before the next delivery.
- With enough events, the 5min plan (title + clips) is 300 ± 15 s.
- With too few events, all are included and the shorter length is reported.
- Wickets are selected before boundaries when competing for space.
- Excluded ids and overturned wickets never appear in the plan.
- Clips are chronological, don't overlap, and offsets match durations.
- Mode all includes every wicket, six and four.
- Caption format matches the examples, including the unknown-over case.
"""

from __future__ import annotations

import pytest

from reel.common.config import load_config
from reel.common.models import ClipBoundary, Delivery, Event
from reel.highlights.rating import rate
from reel.highlights.select import add_clips, caption, clip_for, mode_target_s, plan_reel

CFG = load_config()


def delivery(
    i: int,
    runs: int = 0,
    wicket: bool = False,
    length: float = 40.0,
    overturned: bool = False,
    overs: str | None = "5.1",
) -> Delivery:
    start = i * length
    return Delivery(
        id=f"d{i:03d}",
        over_ball=overs,
        start_s=start,
        t_hit_s=start + 6,
        end_s=start + length,
        runs_delta=runs,
        wicket=wicket,
        overturned=overturned,
        score_after="IND 50/1",
        excitement_max=0.5,
    )


def events_for(deliveries: list[Delivery]) -> list[Event]:
    return add_clips(rate(deliveries, CFG), deliveries, CFG)


def many_events(n: int = 60) -> tuple[list[Delivery], list[Event]]:
    kinds = [(4, False), (6, False), (0, True), (1, False)]
    ds = [delivery(i, *kinds[i % 4]) for i in range(n)]
    return ds, events_for(ds)


class TestClipBoundaries:
    def test_boundary_rule(self) -> None:
        d = delivery(0, runs=4, length=15.0)
        clip = clip_for(events_for([d])[0], d, CFG)
        assert clip.start_s == 0.0  # run-up start is later than t_hit - 6
        assert clip.end_s == pytest.approx(15.0 - 0.5)  # stops before the next delivery
        long = delivery(1, runs=6, length=60.0)
        clip = clip_for(events_for([long])[0], long, CFG)
        assert clip.end_s - clip.start_s <= 25.0 and clip.end_s == long.t_hit_s + 12

    def test_wicket_gets_longer_clip(self) -> None:
        d = delivery(0, wicket=True, length=60.0)
        clip = clip_for(events_for([d])[0], d, CFG)
        assert clip.end_s == d.t_hit_s + 20 and clip.end_s - clip.start_s <= 35


class TestSelection:
    def test_5min_within_tolerance(self) -> None:
        _, events = many_events()
        plan = plan_reel(events, "5min", CFG)
        assert abs(plan.duration_s - 300) <= 15

    def test_few_events_all_included(self) -> None:
        _, events = many_events(4)
        plan = plan_reel(events, "10min", CFG)
        assert len(plan.clips) == 3  # four, six, wicket (the single is not an event)
        assert plan.duration_s < 600 - 15

    def test_wickets_first(self) -> None:
        _, events = many_events()  # 15 wickets x 26 s = 390 s, more than a 3-minute reel
        plan = plan_reel(events, "3min", CFG)
        types = {e.id: e.type for e in events}
        assert plan.clips and all(types[c.event_id] == "wicket" for c in plan.clips)

    def test_excluded_and_overturned_never_selected(self) -> None:
        ds = [delivery(0, wicket=True, overturned=True), delivery(1, runs=4), delivery(2, runs=6)]
        events = events_for(ds)
        plan = plan_reel(events, "all", CFG, exclude={events[1].id})
        assert [c.event_id for c in plan.clips] == [events[2].id]

    def test_order_overlap_offsets(self) -> None:
        ds = [delivery(i, runs=4, length=10.0) for i in range(12)]
        events = events_for(ds)
        # force overlaps by widening clips
        events = [
            e.model_copy(
                update={"clip": ClipBoundary(start_s=e.clip.start_s, end_s=e.clip.end_s + 8)}
            )
            for e in events
        ]
        plan = plan_reel(events, "5min", CFG)
        assert plan.clips[0].offset_s == CFG.highlights.title_card_s
        for a, b in zip(plan.clips, plan.clips[1:]):
            assert a.start_s < b.start_s and a.end_s <= b.start_s
            assert b.offset_s == pytest.approx(a.offset_s + a.duration_s)
        last = plan.clips[-1]
        assert plan.duration_s == pytest.approx(last.offset_s + last.duration_s)

    def test_all_mode(self) -> None:
        _, events = many_events(20)
        plan = plan_reel(events, "all", CFG)
        assert {c.event_id for c in plan.clips} == {e.id for e in events}

    def test_modes(self) -> None:
        assert [mode_target_s(m) for m in ("3min", "5min", "10min", "all")] == [180, 300, 600, None]
        with pytest.raises(ValueError):
            mode_target_s("2hours")


class TestCaptions:
    def test_formats(self) -> None:
        e = events_for([delivery(0, runs=6)])[0].model_copy(
            update={"over_ball": "16.2", "score_text": "IND 151/3"}
        )
        assert caption(e) == "SIX · 16.2 ov · IND 151/3"
        assert caption(e.model_copy(update={"over_ball": None})) == "SIX · IND 151/3"
        moment = e.model_copy(update={"type": "moment", "over_ball": None, "score_text": None})
        assert caption(moment) == "BIG MOMENT"
