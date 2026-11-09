# Slice 43 — Excitement for continuous crowd noise

**Owner:** Dev B · **Sprint:** F2 · **Target week:** 4 · **Depends on:** 38

## Module
`audio`

## What to build
- The crowd part of excitement is compared with its rolling 5-min median/MAD (as loudness already is), rather than being a raw probability, so a constantly singing crowd doesn't read as constant excitement.
- `find_peaks(excitement, cfg)`: 3 s smoothing, prominence and minimum-gap rules from ARCHITECTURE.md, returning times and heights.

## Acceptance criteria
- [ ] Given a constant high crowd probability, then excitement stays near 0.
- [ ] Given a constant crowd with one burst, then excitement peaks at the burst (±2 s).
- [ ] Given two bursts 10 s apart, then one peak (the stronger) is returned.
- [ ] Given bursts 40 s apart, then two peaks are returned.
- [ ] Given the same input, then the output is identical.
- [ ] Human: on a dev match, record the share of `Goal` labels with a peak within ±15 s and the peaks per match.

## Out of scope for this slice
Commentary (slice 45).

## Human review required?
No.
