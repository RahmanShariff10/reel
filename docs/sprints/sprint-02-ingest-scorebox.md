# Sprint 02 — Ingest and score box

**Weeks:** 3–4

## Goal
A real match video goes through the first three pipeline stages: metadata and audio are extracted, the score box is found automatically, and the single full scan produces camera cuts, keyframes and score crops. The web app shows live progress.

## Slices in this sprint
- [ ] `slice-07-ingest` (Dev A) — ffprobe metadata, 32 kHz mono audio extraction
- [ ] `slice-08-scorebox-locate` (Dev A) — automatic score-box detection with validation and a preview frame
- [ ] `slice-09-scan-pass` (Dev B) — the single full decode: camera cuts, keyframes, 2 fps score crops
- [ ] `slice-10-progress-page` (Dev B) — job page that polls status and shows stages

## Human tasks
- [ ] Both: run stages 1–3 on a full real match on both laptops; record time per stage and peak memory here.
- [ ] Dev A: check the detected score box on every collected match; note any failures.

## Depends on
Sprint 01 (slices 01–06).

## Notes for next time
