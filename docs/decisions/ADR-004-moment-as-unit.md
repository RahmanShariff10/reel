# ADR-004 — The candidate moment is the unit of analysis (supersedes ADR-001)

> **Amended by [ADR-007](ADR-007-no-replay-signal.md):** replay runs are not a source in the MVP, because the score graphic stays on during replays.

## Context
Reel moved from cricket to football. Cricket has a repeating unit (the delivery) marked by a camera shot. Football is continuous, with no equivalent shot and no natural segmentation.

## Decision
The pipeline builds a list of candidate moments from three sources (goal events, excitement peaks, replay runs), merges those close in time, and rates each one. Clip boundaries come from the moment's time and the surrounding camera shots.

Cricket support is replaced, not kept alongside football. The last cricket version is git tag `cricket-final`.

## Why
- Goals are too rare to fill a reel, so most clips must come from signals other than the score.
- Merging sources gives one explained event per moment, with every source as a reason.
- A multi-sport plugin layer would add abstraction nobody needs; the PRD covers one sport.

## Alternatives considered
- **Trained action spotting (SoccerNet-style):** more accurate for typed events, but needs a GPU to train and breaks the CPU-only goal.
- **Keep the delivery model and rename it:** there is no football shot that plays the role of `run_up`.
