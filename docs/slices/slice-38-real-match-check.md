# Slice 38 — Real-match assumption check

**Owner:** Dev A · **Sprint:** F1 · **Target week:** 2 · **Depends on:** 35; **needs approved SoccerNet access**

## Module
`eval`

## What to build
`python -m eval.check_assumptions --manifest <games>`, a throwaway measuring script (no pipeline changes) that runs on 3–5 matches from different competitions and writes `eval/reports/assumptions.md`, containing only numbers and no frames:
- **A1, clock:** sample 80 frames per match; report whether a position shows a linear clock (rules in ARCHITECTURE.md), its presence rate and the linearity score.
- **A2, replays:** using the located box and `Labels-cameras.json`, report how often the box is hidden during `replay` shots versus `real-time` shots.
- **A3, audio:** for each `Goal` and `Shots on target` label, report whether an excitement peak falls within ±15 s, plus the peak rate per minute of in-play time.
- **Commentary language** per match.
- A recommendation for each assumption: holds, or what to change.

## Acceptance criteria
- [x] Given synthetic inputs with known answers, then A1, A2 and A3 report them correctly.
- [x] Given a run, then the report contains no images or copied broadcast text beyond team codes.
- [x] Human: the script is run on real matches and the report is reviewed.
- [x] Human: where an assumption fails, ARCHITECTURE.md and the affected slices are updated before slice 39 starts.
- [x] Human: `eval/manifests/matches.yaml` is filled in with English-commentary games.

## Out of scope for this slice
Production detection code (slice 39 onwards).

## Human review required?
Yes: the go/no-go on the assumptions.
