# Slice 17 — Deliveries

**Owner:** Dev A · **Sprint:** 04 · **Target week:** 7–8 · **Depends on:** 12, 15, 16

## Module
`deliveries`

## What to build
The `deliveries` stage writes `deliveries.json`, following ARCHITECTURE.md:
- **Delivery start:** a `run_up` shot whose midpoint falls in a period where the score box is visible. If the score box was not found, every `run_up` shot counts. Consecutive run-up shots less than 3 s apart (config) are merged.
- **`t_hit_s`:** the end of the delivery's run-up shot. **`end_s`:** the next delivery's start (or start + 60 s for the last one).
- **Outcome:** each score event is assigned to the latest delivery that started before it. Set `runs_delta`, `wicket`, `overturned`, `score_after` and `over_ball` (from the score timeline at or after the event, null if unreadable).
- **`replay_count`:** run-up shots with the score box hidden between `t_hit_s` and the next delivery start.
- **`excitement_max`:** the maximum excitement in [start, end].

## Acceptance criteria
- [ ] Given the synthetic stage files, then ≥ 95% of scheduled deliveries are found and no replay is counted as a delivery.
- [ ] Given the synthetic stage files, then every score event is assigned to the correct scheduled delivery.
- [ ] Given the synthetic stage files, then `replay_count` matches the schedule for every delivery.
- [ ] Given `scorebox found: false`, then deliveries come from run-up shots only, outcomes are empty, and the stage succeeds.
- [ ] Given a readable score timeline, then `over_ball` is populated.
- [ ] Human check: on the development match, the number of deliveries is within 10% of Cricsheet's ball count; record it in the sprint 04 notes.

## Out of scope for this slice
Rating and selecting highlights (slices 18–19).

## Human review required?
No.
