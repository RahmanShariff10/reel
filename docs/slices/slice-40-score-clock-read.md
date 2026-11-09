# Slice 40 — Read score and clock

**Owner:** Dev A · **Sprint:** F2 · **Target week:** 3–4 · **Depends on:** 39

*Replaces slice 11.*

## Module
`scoreboard`

## What to build
- `crop_changed` ignores pixels inside `clock_box`.
- OCR changed crops; parse home, away and team codes; a crop with no score is `visible: false`.
- Read the clock every `clock_read_s` from the crop series (not on every crop).
- `parse_score` handles separators `-`, `:`, `|`, or none, and OCR returning one line or several items.

## Acceptance criteria
- [ ] Given a synthetic ticking graphic with an unchanged score, then at most 1 OCR call is made per 30 s of video for the score, plus clock reads.
- [ ] Given a score change, then the changed crop is OCR'd within one crop.
- [ ] Given `ARS 1-0 CHE`, `ARS 1 0 CHE`, `RMA 0 | 0 BAR` and `MCI 2:1 LIV 67:05`, then home and away parse correctly.
- [ ] Given OCR items `['ARS', '1-0', 'CHE', '34:14']`, then the reading is home 1, away 0, clock 34:14.
- [ ] Given a hidden graphic, then the reading is `visible: false`.
- [ ] Human: on a dev match, record the OCR call count and `read_score` time in the sprint notes.

## Out of scope for this slice
Goals and halves (slice 41).

## Human review required?
No.
