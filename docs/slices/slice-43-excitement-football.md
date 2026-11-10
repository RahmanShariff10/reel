# Slice 43 — Excitement for continuous crowd noise

**Owner:** Dev B · **Sprint:** F2 · **Target week:** 4 · **Depends on:** 38

## Module
`audio`

## What to build
- The crowd part of excitement is compared with its rolling 5-min median/MAD (as loudness already is), rather than being a raw probability, so a constantly singing crowd doesn't read as constant excitement.
- `find_peaks(excitement, cfg)`: 3 s smoothing, prominence and minimum-gap rules from ARCHITECTURE.md, returning times and heights.

With replays dropped ([ADR-007](../decisions/ADR-007-no-replay-signal.md)), audio peaks are the only source of non-goal moments. At G1, peaks from the old excitement code matched 11 of 14 goals (79%) but only 22 of 52 shots on target (42%), and ranged from 0.22 to 0.96 per minute between broadcasts.

## Acceptance criteria
- [ ] Given a constant high crowd probability, then excitement stays near 0.
- [ ] Given a constant crowd with one burst, then excitement peaks at the burst (±2 s).
- [ ] Given two bursts 10 s apart, then one peak (the stronger) is returned.
- [ ] Given bursts 40 s apart, then two peaks are returned.
- [ ] Given the same input, then the output is identical.
- [ ] Human: on the dev matches, record the share of `Goal` and `Shots on target` labels with a peak within ±15 s and the peaks per minute, and compare them with the G1 numbers above.

## Out of scope for this slice
Commentary (slice 45).

## Human review required?
No.
