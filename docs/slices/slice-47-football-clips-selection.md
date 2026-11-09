# Slice 47 — Football clip boundaries and selection

**Owner:** Dev A · **Sprint:** F3 · **Target week:** 6 · **Depends on:** 46

*Replaces slice 19.*

## Module
`highlights`

## What to build
Update `select.py` per ARCHITECTURE.md: the clip table by type, half-boundary limit, captions (`GOAL · 67' · ARS 2-1 CHE`), goals-first selection, and the `all` rule.

## Acceptance criteria
- [ ] Given each event type, then clip length follows its pre-roll, post-roll and cap.
- [ ] Given a goal 5 s after a half starts, then the clip doesn't start before the half.
- [ ] Given limited length, then every goal is selected before any other event.
- [ ] Given a chosen mode, then the plan is within ±15 s of the target when enough events exist.
- [ ] Given overlapping clips, then they play in match order with no repeated footage.
- [ ] Given an overturned or excluded event, then it is never selected.
- [ ] Given `all` with a score box, then `moment` and `yellow_card` events are excluded.
- [ ] Given an event with no minute, then the caption omits the minute.

## Out of scope for this slice
Rendering (slice 48).

## Human review required?
No.
