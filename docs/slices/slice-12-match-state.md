# Slice 12 — Match-state machine

**Owner:** Dev A · **Sprint:** 03 · **Target week:** 5–6 · **Depends on:** 11

## Module
`scoreboard`

## What to build
The second half of the `read_score` stage: turn `score_readings.json` into `score_timeline.json` (cleaned state over time, with visibility) and `score_events.json`. Rules from ARCHITECTURE.md "Match-state machine", all thresholds in config:
- **Confirmation:** a new reading is accepted only after ≥ 2 consecutive changed crops.
- **Plausibility:** runs never decrease within an innings; wickets rise by at most 1 per change; a run jump > 13 is rejected; overs going backwards are ignored.
- **Innings:** runs, wickets and overs all dropping to ~0 starts a new innings.
- **DRS:** wickets dropping by 1 within 120 s of a wicket marks that wicket `overturned` and emits `wicket_overturned`.
- **Hidden box:** periods with the box hidden create no events, and the state continues correctly when it reappears.
- **Events:** `runs` (with delta), `wicket`, `wicket_overturned`, `innings_start`, each with time, innings and the score after.

## Acceptance criteria
- [ ] Given the synthetic video, then every scheduled score change produces exactly one event of the right type and delta, within 1 s of the scheduled time.
- [ ] Given a single misread crop injected into readings, then no event is produced.
- [ ] Given a run jump of 20 in one change, then it is rejected.
- [ ] Given the scheduled innings reset, then an `innings_start` event is emitted and later events have innings 2.
- [ ] Given the scheduled DRS reversal, then the wicket is marked `overturned` and a `wicket_overturned` event exists.
- [ ] Given a hidden-box period followed by a changed score, then exactly the correct event is emitted after the box reappears.
- [ ] Given `scorebox.json` with `found: false`, then the stage writes empty outputs and succeeds.

## Out of scope for this slice
Assigning events to deliveries (slice 17).

## Human review required?
No.
