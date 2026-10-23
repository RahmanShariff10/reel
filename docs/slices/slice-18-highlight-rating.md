# Slice 18 — Highlight rating

**Owner:** Dev A · **Sprint:** 04 · **Target week:** 8 · **Depends on:** 17

## Module
`highlights`

## What to build
The rating part of the `highlights` stage writes `events.json` (no clip times yet), using the rules in ARCHITECTURE.md "Highlight rules", with all values in config:
- **Types:** one event per delivery that is a wicket (including overturned, flagged), six (runs delta 6) or four (runs delta 4), with base importance from config.
- **Bonuses:** excitement up to +0.2; +0.05 per replay, capped at +0.15; +0.1 in the last 3 overs of an innings (overs ≥ 17.0) or in a close chase. Importance is capped at 1.0.
- **Fallback:** when the score signal is off or the score box wasn't found, emit `moment` events for deliveries with high excitement and/or replays (thresholds in config).
- **Reasons:** every event lists its reasons, e.g. `{signal: "score", value: 6, label: "score +6"}`, `{signal: "audio", value: 0.82, label: "crowd excitement high"}`, `{signal: "replays", value: 2, label: "2 replays"}`.
- **Confidence:** from score confirmation and the run-up shot probability.

## Acceptance criteria
- [ ] Given a deliveries fixture, then exactly one event is created per wicket, six and four, with the configured base importance.
- [ ] Given excitement, replays and death overs, then the bonuses are applied, the replay bonus is capped at 0.15, and importance never exceeds 1.0.
- [ ] Given any event of type wicket/six/four, then it has a `score` reason, and every reason has a readable label.
- [ ] Given a changed weight in config, then output changes with no code change.
- [ ] Given `signals.audio: false`, then no audio bonus or reason appears.
- [ ] Given `signals.score: false`, then only `moment` events are produced.
- [ ] Given the same input, then `events.json` is identical across runs.

## Out of scope for this slice
Near-miss events (slice 27). Clip times and selection (slice 19).

## Human review required?
No.
