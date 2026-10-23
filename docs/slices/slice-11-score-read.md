# Slice 11 — Score reading

**Owner:** Dev A · **Sprint:** 03 · **Target week:** 5 · **Depends on:** 08, 09

## Module
`scoreboard`

## What to build
The first half of the `read_score` stage: turn score crops into raw readings in `score_readings.json`.
- **Skip unchanged crops:** if a crop's mean absolute pixel difference from the last OCR'd crop is below a threshold (config), copy the previous reading instead of running OCR.
- **OCR** changed crops with RapidOCR.
- **Parse** runs, wickets, overs and team text. Support `145/3`, `145-3`, wickets-runs order (from `scorebox.json`), and overs written as `16.2`, `16.2 ov` or `OVERS 16.2`.
- **Visibility:** mark `visible: false` when no score pattern is found in the crop.

Each reading: `t`, `runs`, `wickets`, `overs`, `team`, `visible`, `raw_text`, `confidence`.

## Acceptance criteria
- [ ] Given parser unit tests for `IND 145/3 16.2`, `145-3`, `3/145` (wickets-runs), `16.2 ov`, `OVERS 16.2` and garbage text, then each parses correctly or returns "no reading".
- [ ] Given the synthetic video, then ≥ 98% of crops in visible periods parse to the schedule's values.
- [ ] Given scheduled hidden-box intervals, then ≥ 95% of crops inside them are `visible: false`.
- [ ] Given the synthetic video, then OCR runs on fewer than 25% of crops (unchanged crops are skipped).
- [ ] Human check: on a full real match, OCR time ≤ 5 min; record it in the sprint 03 notes.

## Out of scope for this slice
Cleaning readings into events (slice 12).

## Human review required?
No.
