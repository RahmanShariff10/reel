# Slice 50 — Football evaluation metrics and report

**Owner:** Dev A · **Sprint:** F5 · **Target week:** 10–11 · **Depends on:** 35, 49

*Replaces slices 13 and 25.*

## Module
`eval`

## What to build
Replace `e1.py` and `metrics.py`, and update `report.py`, with E0, E1, E2, E3, E5 and runtime as defined in ARCHITECTURE.md, reading the manifest from slice 35. Per-match and overall tables with targets from the PRD. Output is numbers only: no frames.

## Acceptance criteria
- [ ] Given goals identical to the labels, then E1 precision and recall are 1.0.
- [ ] Given a goal 31 s from its label, then it counts as both a miss and a false detection.
- [ ] Given events covering 3 of 4 key actions, then E2 is 0.75.
- [ ] Given a goal clip covering label −3 s to +3 s, then E3 counts it; given one starting at label −2 s, then it doesn't.
- [ ] Given a fixed seed, then E5's random baseline is identical across runs.
- [ ] Given a reel with all clips containing key actions, then E5 is 1.0.
- [ ] Given a run, then `summary.md` lists each target as met, not met or n/a.

## Out of scope for this slice
Ablation (slice 26).

## Human review required?
No.
