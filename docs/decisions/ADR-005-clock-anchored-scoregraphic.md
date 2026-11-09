# ADR-005 — Find the score graphic by its clock; the score only yields goals (supersedes ADR-002)

## Context
Cricket's score changes on nearly every highlight, so it could be the primary signal. Football's changes two or three times a match. Football graphics also show a ticking clock, and many show the score with no separator (`ARS 1 0 CHE`).

## Decision
- Locate the graphic by a clock token whose value advances at about one second per second of video.
- Treat score changes as near-certain goals, and nothing more.
- OCR the score only when pixels outside the clock changed; read the clock every 30 s.

## Why
- A running clock is far harder to mistake for other text than a score pattern is, and works when the score has no separator.
- The clock gives match minutes, halves and an in-play window, which removes pre-match and half-time.
- Running the cricket "unchanged crop" check on a ticking graphic sent 50% of crops to OCR in a test (about 7,200 calls for a two-hour broadcast).

## Alternatives considered
- **Reuse score-pattern detection:** `ARS 1 0 CHE` and `MCI 2:1 LIV` failed to parse in a test of the cricket parser.
- **Trained scoreboard detector:** needs labelled data per broadcaster.

## To confirm
Slice 38 checks this on real broadcasts.
