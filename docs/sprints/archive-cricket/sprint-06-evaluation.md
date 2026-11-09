# Sprint 06 — Evaluation

**Weeks:** 11–12

## Goal
Reproducible evaluation on the held-out test matches: event detection, delivery detection, clip accuracy, processing time, signal ablation and agreement with official highlights. Config is tuned on the development matches only.

## Slices in this sprint
- [ ] `slice-25-eval-metrics` (Dev A) — E2 delivery detection, E3 clip accuracy, runtime, aggregated report
- [ ] `slice-26-eval-ablation` (Dev B) — E4 ablation runner, E5 agreement with official highlights

## Human tasks
- [ ] Both: annotate the 2–3 test matches (timestamps of every boundary and wicket).
- [ ] Both: for each test match, list the over.ball of every delivery in the official highlights (`eval/annotations/official_*.csv`).
- [ ] Dev A: tune `config/default.yaml` on the development matches; freeze it before running on test matches.
- [ ] Dev B: prepare the viewer survey (E6): 3 reels per match (ours, random clips, official), rating form, 10–15 participants.

## Depends on
Sprint 05.

## Notes for next time
