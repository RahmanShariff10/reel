# Slice 19 — Clip boundaries and selection

**Owner:** Dev A · **Sprint:** 04 · **Target week:** 8–9 · **Depends on:** 18

## Module
`highlights`

## What to build
The selection part of the `highlights` stage. For a given `mode` (`3min`, `5min`, `10min`, `all`) and optional `exclude_event_ids`:
- **Clip times for every event** (written into `events.json`):
  - start = max(run-up start, `t_hit − 6 s`);
  - end = `t_hit + 12 s` for a four or six, `t_hit + 20 s` for a wicket;
  - never past the next delivery start − 0.5 s;
  - capped at 25 s for boundaries and 35 s for wickets (all values in config).
- **Selection:**
  1. Wickets go in first, then other events by importance, until adding the next clip would exceed the target.
  2. The title card (3 s) and fades count towards the length; the result must be within ±15 s.
  3. `all` includes every wicket, six and four.
  4. Overturned wickets and excluded ids are never selected.
  5. Overlapping clips are trimmed so they don't overlap.
- **Captions:** e.g. `SIX · 16.2 ov · IND 151/3`. The over part is omitted if unknown, and `moment` events are captioned `BIG MOMENT`.
- **Output:** `reel_plan_<mode>.json` with clips in match order, each with its offset in the reel.

## Acceptance criteria
- [ ] Given a boundary event, then its clip times follow the rule above, and the clip is ≤ 25 s and ends before the next delivery.
- [ ] Given enough events, when mode is `5min`, then the planned reel length (including title and fades) is 300 ± 15 s.
- [ ] Given too few events for the target, then all events are included and the shorter length is reported.
- [ ] Given wickets and boundaries competing for space, then wickets are selected first.
- [ ] Given excluded ids or overturned wickets, then they never appear in the plan.
- [ ] Given the plan, then clips are in chronological order, don't overlap, and offsets are consistent with durations.
- [ ] Given mode `all`, then every wicket, six and four appears.
- [ ] Caption format matches the examples, including the unknown-over case.

## Out of scope for this slice
Rendering (slices 20–21).

## Human review required?
No.
