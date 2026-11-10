# Slice 46 — Football highlight rating

**Owner:** Dev A · **Sprint:** F3 · **Target week:** 6 · **Depends on:** 44, 45

*Replaces slices 18 and 27 (near-misses are now `chance` and `moment` events).*

## Module
`highlights`

## What to build
Rewrite `rating.py` per ARCHITECTURE.md's Highlight rules: base importance, bonuses, the qualification test for non-goal moments, confidence, and reasons. There is no replay bonus or reason ([ADR-007](../decisions/ADR-007-no-replay-signal.md)).

## Acceptance criteria
- [ ] Given a goal moment, then the event is `goal` with a `score +1` reason and importance capped at 1.0.
- [ ] Given a `chance` keyword and excitement 0.8, then the event is `chance` with audio and commentary reasons.
- [ ] Given a `penalty` keyword during quiet play, then no event is created.
- [ ] Given minute 85 with the score within one goal, then the late bonus applies with a reason; with a three-goal gap it doesn't.
- [ ] Given `found: false` and an exciting moment, then the event is `moment`.
- [ ] Given `signals.audio` or `signals.commentary` off, then that signal adds no bonus or reason.
- [ ] Given an overturned goal, then the event is flagged `overturned`.

## Out of scope for this slice
Clip boundaries and selection (slice 47).

## Human review required?
No.
