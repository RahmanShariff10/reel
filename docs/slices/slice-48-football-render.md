# Slice 48 — Football title card and summary

**Owner:** Dev B · **Sprint:** F3 · **Target week:** 6 · **Depends on:** 44, 47

## Module
`render`

## What to build
Update `render/reel.py`: title card from team codes and final score, mode labels ("All goals and key moments"), and `Summary` (`final_score`, `halves`, `moments_found`). Clip rendering stays as it is, including the caption avoiding the score graphic.

## Acceptance criteria
- [ ] Given moments ending `ARS 2-1 CHE`, then the title card shows `ARS vs CHE` and `2-1` (checked by OCR).
- [ ] Given no score box, then the title card reads "Match highlights" and the render succeeds.
- [ ] Given mode `all`, then the label is "All goals and key moments".
- [ ] Given goals in both halves, then `summary.halves` counts them per half and side.
- [ ] Given the synthetic match, then the reel plays and its duration matches the plan (±1 s).

## Out of scope for this slice
Vertical export (slice 33).

## Human review required?
No.
