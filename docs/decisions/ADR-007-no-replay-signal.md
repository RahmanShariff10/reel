# ADR-007 — No replay signal in the MVP (amends ADR-004)

## Context
ADR-004 used replay runs (the score graphic hidden for ≥ 3 s) as one of three sources of candidate moments, and the rating gave a bonus per replay. Slice 38 measured this on 5 real broadcasts from 5 competitions ([report](../../eval/reports/assumptions.md)): the graphic was hidden in 2% of replay shots and 3% of live shots. It stays on during replays, so a hidden graphic can't mark one.

## Decision
The MVP finds moments from goal events and crowd-audio peaks only, and commentary types them. There is no replay source, replay count, replay bonus or replay ablation step. Leftover replay names in code and config are removed in slice 49.

## Why
- There is no cheap working detector. Building one, by training on SoccerNet's `replay` camera flag or by detecting the broadcaster's replay transitions, is new work of unknown accuracy that would land before slice 44, and the MVP date is fixed.
- Goals still come from the clock-anchored score graphic, which held on 5 of 5 matches.

## Consequences
- Audio peaks are the only source of non-goal moments. At G1 they matched 22 of 52 shots on target, so slice 43's crowd baseline matters more.
- Revisit after G2: if E2 (key-action recall) misses its target, try a replay classifier trained on SoccerNet's `replay` flag using the existing CLIP shot embeddings.
