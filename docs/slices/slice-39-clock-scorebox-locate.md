# Slice 39 — Locate the score graphic by its clock

**Owner:** Dev A · **Sprint:** F2 · **Target week:** 3 · **Depends on:** 36, 37, 38

*Replaces slice 08.*

## Module
`scoreboard`

## What to build
Rework `locate_scorebox` per ARCHITECTURE.md:
- clock-token parsing in `parse.py`;
- clusters by screen position, keeps those present in ≥ 40% of samples;
- the linearity check;
- finds the adjacent score and `clock_box`, including the merged-text case;
- grows and pads the box as today; saves `scorebox_preview.jpg` always.

## Acceptance criteria
- [x] Given synthetic videos in each graphic style, then the box is found within 10 px of the true position.
- [x] Given a static `12:30` caption elsewhere on screen, then it is not selected.
- [x] Given a video with no graphic, then `found: false` and the stage succeeds.
- [x] Given OCR that merges clock and score into one item, then `clock_box` still covers the clock digits.
- [x] Given `MCI 2:1 LIV 67:05`, then `2:1` is not taken for a clock and `67:05` is.
- [x] Given `45:00+2`, then it parses as a clock of 45:00 plus 2 added minutes.
- [x] Human: found on the dev matches; record the results in the sprint notes.

## Out of scope for this slice
Reading every crop (slice 40).

## Human review required?
No.
