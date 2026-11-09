# Slice 37 — Synthetic football fixtures

**Owner:** Dev B · **Sprint:** F1 · **Target week:** 1–2 · **Depends on:** 36

## Module
tests

## What to build
Rewrite `tests/fixtures/make_synthetic.py` as a scripted football broadcast with a `schedule.json`:
- scenes per `ShotLabel`, with hard cuts;
- a score graphic at a fixed position with a **ticking clock**, and a configurable style: `ARS 1-0 CHE`, `ARS 1 0 CHE`, `ARS 1:0 CHE`;
- goals with the score updating a known lag after the goal;
- one replay with the graphic hidden, one overturned goal, one half-time break with no graphic and a clock restart;
- audio: background noise with bursts at known times, including a burst with no goal (a chance).

## Acceptance criteria
- [x] Given a generated video, then duration, resolution and audio match the request.
- [x] Given the schedule, then it lists goals, score-update times, replays, half boundaries, bursts and shots.
- [x] Given the same seed, then the schedule is identical.
- [x] Given each graphic style, then a sampled frame's OCR contains the score and clock from the schedule at that time.
- [x] Given the schedule, then at least one goal, one overturned goal, one replay, one half-time break and one no-goal burst are included.
- [x] Given the fixture, then the generator runs in under 60 s for a 3-minute video.

## Out of scope for this slice
Realistic visuals.

## Human review required?
No.
