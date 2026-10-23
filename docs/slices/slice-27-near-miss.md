# Slice 27 — Near-miss moments

**Owner:** Dev A · **Sprint:** 07 · **Target week:** 12–13 · **Depends on:** 18, 19, 24

## Module
`highlights` (small change in `frontend`)

## What to build
- **Rule:** a delivery with no score change, `excitement_max` ≥ threshold (default 0.7) and `replay_count` ≥ 1 becomes a `near_miss` event with base importance 0.5. Thresholds are in config, and it's switched on/off by `highlights.near_miss.enabled` (default true).
- **Reasons and caption:** reasons as usual; caption `BIG MOMENT · 12.4 ov`.
- **Selection:** near-misses are considered after wickets and boundaries.
- **Frontend:** a distinct badge for `near_miss` in the event list.

## Acceptance criteria
- [ ] Given a delivery with no score change, excitement 0.8 and 1 replay, then a `near_miss` event is created with an excitement reason and a replay reason.
- [ ] Given the same delivery with 0 replays, then no event is created.
- [ ] Given `near_miss.enabled: false`, then no near-miss events appear.
- [ ] Given limited reel length, then wickets and boundaries are selected before any near-miss.
- [ ] Given the results page, then near-miss events show their own badge.

## Out of scope for this slice
Classifying what kind of near-miss it was (dropped catch, appeal, etc.).

## Human review required?
No.
