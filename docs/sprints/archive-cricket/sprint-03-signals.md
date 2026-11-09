# Sprint 03 — Signals

**Weeks:** 5–7

## Goal
All three signals exist for a real match: score events from the score box (with innings and DRS handling), a type label for every camera shot, and per-second crowd excitement. The evaluation foundation can already score event detection against Cricsheet.

## Slices in this sprint
- [ ] `slice-11-score-read` (Dev A) — OCR on changed crops only, score parsing, visibility
- [ ] `slice-12-match-state` (Dev A) — match-state machine → score timeline and score events
- [ ] `slice-13-eval-foundation` (Dev A) — Cricsheet loader, annotation format, E1 event-accuracy metric
- [ ] `slice-14-shot-clip-zeroshot` (Dev B) — CLIP embeddings (cached) and zero-shot shot labels
- [ ] `slice-15-shot-classifier` (Dev B) — labelling tool, classifier training, classifier in the pipeline
- [ ] `slice-16-audio-excitement` (Dev B) — loudness z-score + PANNs → excitement per second

## Human tasks
- [ ] Dev B: label ~500 keyframes from the development matches with the labelling tool (slice 15).
- [ ] Dev A: annotate the development match: video timestamp of every boundary and wicket (`eval/annotations/`).
- [ ] Dev B: check the licence of the FPV dataset (Abbas et al. 2025); use it for training only if permitted.

## Depends on
Sprint 02 (slices 07–09).

## Notes for next time
