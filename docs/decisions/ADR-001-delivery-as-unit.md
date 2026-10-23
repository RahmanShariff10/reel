# ADR-001 — The delivery (one ball) is the unit of analysis

## Context
Generic highlight systems (e.g. football action spotting) score a match second by second and pick peaks. Cricket is structured as discrete deliveries, each following the same broadcast pattern: bowler run-up from behind the bowler → shot → cut away → optional replays → next ball.

## Decision
The pipeline splits the match into deliveries (a `run_up` camera shot with the score box visible marks a new ball) and rates each delivery. Per-second signals (audio excitement, score changes) are aggregated per delivery.

## Why
- Matches how cricket highlights are actually edited: one clip = one ball, from run-up to outcome.
- Gives natural clip boundaries (run-up start → next ball) instead of arbitrary padding around a peak.
- Lets score-graphic changes be attached to a specific ball, and lets evaluation be done per ball against Cricsheet ball-by-ball data.
- Confirmed by prior work: JioStar's highlight system follows the match "delivery by delivery", and the Amazon 2026 study treats delivery-start detection as a core task.

## Alternatives considered
- **Per-second scoring with peak picking:** simpler and sport-agnostic, but gives poor clip boundaries and can't be checked against ball-by-ball ground truth. Still used internally for audio excitement.
