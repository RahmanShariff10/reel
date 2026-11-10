# Slice 44 — Candidate moments

**Owner:** Dev A · **Sprint:** F3 · **Target week:** 5 · **Depends on:** 41, 42, 43

*Replaces slice 17.*

## Module
`moments` (new; the `deliveries` module is removed)

## What to build
The `moments` stage writes `moments.json`, following ARCHITECTURE.md: the two sources (goal events and audio peaks), merging, `t_moment_s` for goals, `play_start_s`, `excitement_max`, `minute` (from the clock, including `45+2` style) and `score_after`. Only in-play times produce moments. Replays are not a source ([ADR-007](../decisions/ADR-007-no-replay-signal.md)); leave `Moment.replay_count` at its default, since slice 49 removes it.

## Acceptance criteria
- [ ] Given the synthetic stage files, then every scheduled goal has a moment with `goal: true`, and `t_moment_s` is within 3 s of the scheduled goal, not the score update.
- [ ] Given the no-goal burst, then a moment exists with source `audio`.
- [ ] Given a goal and its audio peak within 25 s, then exactly one moment lists both sources.
- [ ] Given a burst during half-time, then no moment is created.
- [ ] Given `found: false`, then moments come from audio only, and the stage succeeds.
- [ ] Given the fixture's replay with the graphic hidden, then no moment is created from it and no moment lists a `replay` source.
- [ ] Given the clock at 47:30 in the first half, then `minute` is `45+3`.

## Out of scope for this slice
Types and rating (slices 45–46).

## Human review required?
No.
