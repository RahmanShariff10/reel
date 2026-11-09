# Slice 41 — Goal state machine and halves

**Owner:** Dev A · **Sprint:** F2 · **Target week:** 4 · **Depends on:** 40

*Replaces slice 12.*

## Module
`scoreboard`

## What to build
Replace `state.py` per ARCHITECTURE.md's goal state machine: confirmation, exactly-one-side-plus-one, overturned goals, half detection, `in_play`, and `clock_s` interpolation between clock reads. Writes `score_timeline.json` and `score_events.json`.

## Acceptance criteria
- [ ] Given the synthetic readings, then every scheduled goal is emitted on the right side at the update time (±1 s).
- [ ] Given a one-off misread `7-0` between `1-0` readings, then no event is emitted.
- [ ] Given a jump from `1-0` to `3-0`, then it is rejected.
- [ ] Given `1-0` back to `0-0` within 300 s, then the goal is `overturned` and `goal_overturned` is emitted.
- [ ] Given the same drop after 300 s, then it is rejected and the score stands.
- [ ] Given the half-time break, then a `half_start` is emitted, and `in_play` is false during the break and before kick-off.
- [ ] Given a clock that restarts at `45:00` or at `00:00`, then both are handled as a new half.
- [ ] Given extra time with the clock running past `90:00`, then the timeline continues without a false half.

## Out of scope for this slice
Moments (slice 44).

## Human review required?
No.
